import asyncio
import discord
from discord import app_commands
from discord.ext import tasks, commands
from callbacks.buttoncallback import build_prediction_view
from match_message import parse_match_time, render_match_message
from checks import owner_only
from API import polymarket
from datetime import datetime, timezone, timedelta
import config

PLACEHOLDER_TEAMS = {None, '', 'TBD'}


class PredictionBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.api_handler = bot.api_handler
        # the background loop and /refresh must never run at the same time, or a match could be posted twice
        self.cycle_lock = asyncio.Lock()

    async def cog_load(self):
        self.check_matches.change_interval(minutes=config.UPDATE_INTERVAL_MINUTES)
        self.check_matches.start()

    async def cog_unload(self):
        self.check_matches.cancel()

    @tasks.loop(minutes=10)
    async def check_matches(self):
        try:
            await self.run_cycle()
        except Exception as e:
            # don't let an unexpected error kill the loop for the rest of the tournament
            print(f"An error occurred in check_matches: {e}")

    @check_matches.before_loop
    async def before_check_matches(self):
        await self.bot.wait_until_ready()

    async def run_cycle(self):
        async with self.cycle_lock:
            # refresh data first so newly scheduled matches, reschedules and results are picked up in the same run
            await self.api_handler.update_match_data()

            channel = self.bot.get_channel(config.CHANNEL_ID)
            if channel is None:
                print(f"Channel {config.CHANNEL_ID} not found, check CHANNEL_ID.")
                return

            markets = await self.fetch_markets()
            await self.post_new_matches(channel, markets)
            await self.update_posted_messages(markets)

    async def fetch_markets(self):
        """Polymarket's match-winner markets, or None if disabled or unreachable (the bot works fine without them)."""
        if not config.POLYMARKET_ENABLED:
            return None
        try:
            return await polymarket.fetch_series_markets()
        except Exception as e:
            print(f"Could not fetch Polymarket odds: {type(e).__name__}: {e}")
            return None

    def store_odds(self, markets, match_id, team1, team2, datetime_utc, closing=False):
        """Saves the match's odds if polymarket has a market for it. Returns True if odds were saved."""
        if markets is None:
            return False
        odds = polymarket.find_odds(markets, team1, team2, parse_match_time(datetime_utc))
        if odds is None:
            return False
        self.db.save_market_odds(match_id, odds[0], odds[1], odds[2], closing)
        return True

    async def post_new_matches(self, channel, markets=None):
        now = datetime.now(timezone.utc)
        upcoming_matches = self.db.get_upcoming_matches(now, now + timedelta(days=config.POST_WINDOW_DAYS))

        for match in upcoming_matches:
            match_id, tournament, datetime_utc, best_of, team1, team2 = match[:6]

            if self.db.get_posted_message(match_id):
                continue
            # wait until both teams are decided (swiss rounds, knockouts) and the format is known
            if team1 in PLACEHOLDER_TEAMS or team2 in PLACEHOLDER_TEAMS or best_of not in (1, 3, 5):
                continue
            # discord limits custom_id to 100 characters
            if len(f"predict${match_id}$0-0") > 100:
                print(f"Match id too long for a button, skipping: {match_id}")
                continue

            self.store_odds(markets, match_id, team1, team2, datetime_utc)
            message = await channel.send(render_match_message(self.db, match_id, 'open'), view=build_prediction_view(match_id, best_of))
            self.db.save_posted_message(match_id, channel.id, message.id, 'open')
            print(f"Posted prediction message for {team1} vs {team2}.")

    async def update_posted_messages(self, markets=None):
        now = datetime.now(timezone.utc)

        for posted in self.db.get_unfinished_posted_messages():
            match_id, channel_id, message_id, state, tournament, datetime_utc, best_of, team1, team2, winner, team1_score, team2_score = posted
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                continue

            match_time = parse_match_time(datetime_utc)
            odds = self.db.get_market_odds(match_id)
            odds_added = False
            if state == 'open' and winner not in (1, 2):
                if now >= match_time - timedelta(minutes=config.UPDATE_INTERVAL_MINUTES) and not (odds and odds[3]):
                    # last update before the start: these become the closing odds shown after the lock
                    # (also catches the start being missed, e.g. after a restart, as long as it's only just begun)
                    if now <= match_time + timedelta(minutes=15):
                        self.store_odds(markets, match_id, team1, team2, datetime_utc, closing=True)
                elif odds is None:
                    # polymarket often lists a match a few days later than it gets posted here
                    odds_added = self.store_odds(markets, match_id, team1, team2, datetime_utc)

            if winner in (1, 2):
                new_state = 'final'
            elif now >= match_time:
                new_state = 'locked'
            elif state == 'open':
                if odds_added:
                    try:
                        await channel.get_partial_message(message_id).edit(content=render_match_message(self.db, match_id, 'open'))
                    except discord.HTTPException as e:
                        print(f"Could not add odds to the prediction message for {match_id}: {e}")
                continue
            else:
                # match was rescheduled to a later time after it was locked, reopen it
                new_state = 'open'

            if new_state == state:
                continue

            try:
                await channel.get_partial_message(message_id).edit(
                    content=render_match_message(self.db, match_id, new_state),
                    view=build_prediction_view(match_id, best_of, disabled=new_state != 'open')
                )
            except discord.NotFound:
                print(f"Prediction message for {match_id} was deleted, no longer tracking it.")
                new_state = 'final'
            except discord.HTTPException as e:
                print(f"Could not edit prediction message for {match_id}: {e}")
                continue

            self.db.set_posted_message_state(match_id, new_state)

    def current_state(self, match_id):
        match = self.db.get_match_details(match_id)
        winner, datetime_utc = match[6], match[2]
        if winner in (1, 2):
            return 'final'
        return 'locked' if datetime.now(timezone.utc) >= parse_match_time(datetime_utc) else 'open'

    async def refresh_match_message(self, match_id, repost=False):
        """
        Re-renders a match's message from the current data (e.g. after /setresult), or posts it again (/repost).
        Returns the message, or None if it couldn't be found or posted.
        """
        async with self.cycle_lock:
            match = self.db.get_match_details(match_id)
            if match is None:
                return None
            best_of = match[3]
            state = self.current_state(match_id)
            content = render_match_message(self.db, match_id, state)
            view = build_prediction_view(match_id, best_of, disabled=state != 'open')
            posted = self.db.get_posted_message(match_id)

            if posted and not repost:
                channel = self.bot.get_channel(posted[0])
                if channel is None:
                    return None
                try:
                    message = await channel.get_partial_message(posted[1]).edit(content=content, view=view)
                except discord.NotFound:
                    return None
                self.db.set_posted_message_state(match_id, state)
                return message

            if posted:
                # remove the old copy so there is only one set of buttons per match
                old_channel = self.bot.get_channel(posted[0])
                if old_channel is not None:
                    try:
                        await old_channel.get_partial_message(posted[1]).delete()
                    except discord.HTTPException:
                        pass
            channel = self.bot.get_channel(config.CHANNEL_ID)
            if channel is None:
                return None
            message = await channel.send(content, view=view)
            self.db.save_posted_message(match_id, channel.id, message.id, state)
            return message

    @app_commands.command(name="refresh", description="Fetch match data from Leaguepedia right now (bot owner only)")
    @app_commands.default_permissions(manage_guild=True)
    @owner_only()
    async def refresh(self, interaction: discord.Interaction):
        # leaguepedia can take a few seconds, slash commands must respond within 3
        await interaction.response.defer(ephemeral=True)
        await self.run_cycle()
        await interaction.followup.send("Match data refreshed.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(PredictionBot(bot))
