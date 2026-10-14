import asyncio
import discord
from discord.ext import tasks, commands
from callbacks.buttoncallback import build_prediction_view
from datetime import datetime, timezone, timedelta
import config

PLACEHOLDER_TEAMS = {None, '', 'TBD'}


def parse_match_time(datetime_utc):
    return datetime.strptime(datetime_utc, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)


def match_header(team1, team2, best_of, tournament, match_time):
    # discord timestamps render in each user's own timezone, :R shows a live countdown
    ts = int(match_time.timestamp())
    return f"**{team1}** vs **{team2}**\nBo{best_of} · {tournament}\n<t:{ts}:F> (<t:{ts}:R>)"


class PredictionBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.api_handler = bot.api_handler
        # the hourly loop and !refresh must never run at the same time, or a match could be posted twice
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

            await self.post_new_matches(channel)
            await self.update_posted_messages()

    async def post_new_matches(self, channel):
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

            match_time = parse_match_time(datetime_utc)
            message = await channel.send(match_header(team1, team2, best_of, tournament, match_time), view=build_prediction_view(match_id, best_of))
            self.db.save_posted_message(match_id, channel.id, message.id, 'open')
            print(f"Posted prediction message for {team1} vs {team2}.")

    async def update_posted_messages(self):
        now = datetime.now(timezone.utc)

        for posted in self.db.get_unfinished_posted_messages():
            match_id, channel_id, message_id, state, tournament, datetime_utc, best_of, team1, team2, winner, team1_score, team2_score = posted
            match_time = parse_match_time(datetime_utc)
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                continue

            if winner in (1, 2):
                new_state = 'final'
            elif now >= match_time:
                new_state = 'locked'
            elif state == 'open':
                continue
            else:
                # match was rescheduled to a later time after it was locked, reopen it
                new_state = 'open'

            if new_state == state:
                continue

            content = match_header(team1, team2, best_of, tournament, match_time)
            if new_state == 'locked':
                content += "\n🔒 Predictions are closed."
            elif new_state == 'final':
                content += "\n" + self.result_summary(match_id, team1, team2, winner, team1_score, team2_score)

            try:
                await channel.get_partial_message(message_id).edit(
                    content=content,
                    view=build_prediction_view(match_id, best_of, disabled=new_state != 'open')
                )
            except discord.NotFound:
                print(f"Prediction message for {match_id} was deleted, no longer tracking it.")
                new_state = 'final'
            except discord.HTTPException as e:
                print(f"Could not edit prediction message for {match_id}: {e}")
                continue

            self.db.set_posted_message_state(match_id, new_state)

    def result_summary(self, match_id, team1, team2, winner, team1_score, team2_score):
        predictions = self.db.get_match_predictions(match_id)
        correct_winner = sum(1 for _, predicted_winner, _, _ in predictions if predicted_winner == winner)
        exact = sum(1 for _, _, p1, p2 in predictions if p1 == team1_score and p2 == team2_score)

        winner_name = team1 if winner == 1 else team2
        score = f" {team1_score}-{team2_score}" if team1_score is not None and team2_score is not None else ""
        return (f"✅ **{winner_name}** won{score}.\n"
                f"{correct_winner}/{len(predictions)} predicted the winner, {exact} got the exact score.")

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def refresh(self, ctx):
        """Force a match data refresh right now (admins only)."""
        await ctx.send("Refreshing match data...")
        await self.run_cycle()
        await ctx.send("Done.")


async def setup(bot):
    await bot.add_cog(PredictionBot(bot))
