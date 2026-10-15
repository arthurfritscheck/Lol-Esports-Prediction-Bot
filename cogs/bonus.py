import discord
from discord import app_commands
from discord.ext import tasks, commands
from datetime import datetime, timezone
from tournament import (BONUS_CATEGORIES, BonusResults, bonus_lock_time, bonus_team_options, score_bonus, format_bonus_picks)
from cogs.commands import chunk_lines
import config


def bonus_points_text():
    return " · ".join(f"{info['label']}: {info['points']} per correct team" if info['picks'] > 1 else f"{info['label']}: {info['points']}"
                      for info in BONUS_CATEGORIES.values())


def timestamp(dt, style='F'):
    return f"<t:{int(dt.timestamp())}:{style}>"


class BonusSelect(discord.ui.Select):
    def __init__(self, category, teams, current):
        info = BONUS_CATEGORIES[category]
        super().__init__(
            placeholder=f"{info['label']} (pick {info['picks']})",
            min_values=info['picks'],
            max_values=info['picks'],
            options=[discord.SelectOption(label=team, value=team, default=team in current) for team in teams],
        )
        self.category = category

    async def callback(self, interaction: discord.Interaction):
        await self.view.handle_pick(interaction, self)


class BonusView(discord.ui.View):
    """The private /bonus form: one dropdown per category, every change is saved straight away."""

    def __init__(self, db, user, teams, lock_time):
        super().__init__(timeout=900)
        self.db = db
        self.user = user
        self.lock_time = lock_time
        current = self.current_picks()
        for category in BONUS_CATEGORIES:
            self.add_item(BonusSelect(category, teams, current.get(category, [])))

    def current_picks(self):
        picks = {}
        for _, _, category, team in self.db.get_bonus_picks(self.user.id):
            picks.setdefault(category, []).append(team)
        return picks

    def summary(self, warning=None):
        picks = self.current_picks()
        lines = [f"**Your bonus predictions** — you can change them until {timestamp(self.lock_time)} ({timestamp(self.lock_time, 'R')})", ""]
        lines += format_bonus_picks({category: [(team, None) for team in teams] for category, teams in picks.items()}, show_status=False)

        notes = []
        missing = [info['label'] for category, info in BONUS_CATEGORIES.items() if category not in picks]
        if missing:
            notes.append(f"Still to pick: {', '.join(missing)}.")
        if picks.get('winner') and picks.get('finalist') and picks['winner'][0] not in picks['finalist']:
            notes.append("Heads up: your tournament winner isn't one of your finalists.")
        if warning:
            notes.insert(0, f"⚠️ {warning}")
        if notes:
            lines += [""] + notes
        lines += ["", f"Points: {bonus_points_text()}"]
        return "\n".join(lines)

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.user.id

    async def handle_pick(self, interaction: discord.Interaction, select: BonusSelect):
        # re-read the lock time, the swiss schedule can change while the form is open
        self.lock_time = bonus_lock_time(self.db.get_full_matches()) or self.lock_time
        if datetime.now(timezone.utc) >= self.lock_time:
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(content="Bonus predictions are locked, the swiss stage has started.", view=self)
            return

        chosen = list(select.values)
        warning = None
        # a team can't go both 3-0 and 0-3
        opposite = {'swiss_3_0': 'swiss_0_3', 'swiss_0_3': 'swiss_3_0'}.get(select.category)
        overlap = set(chosen) & set(self.current_picks().get(opposite, [])) if opposite else set()
        if overlap:
            warning = f"{', '.join(sorted(overlap))} can't go both 3-0 and 0-3, that pick wasn't saved."
        else:
            self.db.set_bonus_picks(self.user.id, self.user.display_name, select.category, chosen)
            print(f"{self.user.display_name} set bonus {select.category}: {', '.join(chosen)}")

        # keep every dropdown showing what is actually saved
        current = self.current_picks()
        for item in self.children:
            if isinstance(item, BonusSelect):
                saved = current.get(item.category, [])
                for option in item.options:
                    option.default = option.value in saved

        await interaction.response.edit_message(content=self.summary(warning), view=self)


class Bonus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    async def cog_load(self):
        self.announce_loop.start()

    async def cog_unload(self):
        self.announce_loop.cancel()

    def all_picks_lines(self):
        results = BonusResults(self.db.get_full_matches())
        users = score_bonus(self.db.get_bonus_picks(), results)
        lines = []
        for data in sorted(users.values(), key=lambda d: (-d['points'], d['username'].lower())):
            lines.append(f"__**{data['username']}**__ — {data['points']} bonus points")
            lines += format_bonus_picks(data['picks'])
            lines.append("")
        return lines

    @app_commands.command(name="bonus", description="Predict the tournament winner, finalists and swiss 3-0 / 0-3 teams")
    async def bonus(self, interaction: discord.Interaction):
        lock_time = bonus_lock_time(self.db.get_full_matches())
        teams = bonus_team_options(self.db.get_teams())
        if lock_time is None or not teams:
            await interaction.response.send_message("Bonus predictions aren't available yet, the teams or the swiss schedule aren't known.", ephemeral=True)
            return

        if datetime.now(timezone.utc) < lock_time:
            view = BonusView(self.db, interaction.user, teams, lock_time)
            await interaction.response.send_message(view.summary(), view=view, ephemeral=True)
            return

        # after the lock everyone's picks are public
        lines = self.all_picks_lines()
        if not lines:
            await interaction.response.send_message("Nobody made bonus predictions.", ephemeral=True)
            return
        chunks = chunk_lines(lines)
        embeds = [discord.Embed(title="Bonus Predictions" if i == 0 else None, description=chunk, color=0xf1c40f) for i, chunk in enumerate(chunks)]
        await interaction.response.send_message(embeds=embeds[:10], ephemeral=True)

    @tasks.loop(minutes=5)
    async def announce_loop(self):
        try:
            await self.announce()
        except Exception as e:
            print(f"An error occurred in the bonus announcements: {e}")

    @announce_loop.before_loop
    async def before_announce_loop(self):
        await self.bot.wait_until_ready()

    async def announce(self):
        channel = self.bot.get_channel(config.CHANNEL_ID)
        lock_time = bonus_lock_time(self.db.get_full_matches())
        if channel is None or lock_time is None or not bonus_team_options(self.db.get_teams()):
            return
        now = datetime.now(timezone.utc)

        if now < lock_time and not self.db.get_state('bonus_announced'):
            await channel.send(
                "🏆 **Bonus predictions are open!**\n"
                "Use `/bonus` to predict the tournament winner, the two finalists, and which two teams go 3-0 and 0-3 in the swiss stage.\n"
                f"Your picks stay hidden until they lock at {timestamp(lock_time)} ({timestamp(lock_time, 'R')}).\n"
                f"Points: {bonus_points_text()}"
            )
            self.db.set_state('bonus_announced', now.isoformat())
            print("Announced bonus predictions.")

        if now >= lock_time and not self.db.get_state('bonus_revealed'):
            lines = self.all_picks_lines()
            if lines:
                chunks = chunk_lines(lines)
                for i, chunk in enumerate(chunks):
                    title = "🔒 Bonus predictions are locked, here's what everyone picked" if i == 0 else None
                    await channel.send(embed=discord.Embed(title=title, description=chunk, color=0xf1c40f))
            self.db.set_state('bonus_revealed', now.isoformat())
            print("Revealed bonus predictions.")


async def setup(bot):
    await bot.add_cog(Bonus(bot))
