import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
from formatting import discord_time
from checks import owner_only
import config

PLACEHOLDER_TEAMS = {None, '', 'TBD'}


class Admin(commands.Cog):
    """Owner-only tools. Discord hides them from members without Manage Server, and owner_only() blocks other admins."""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    async def match_autocomplete(self, interaction: discord.Interaction, current: str):
        """Suggests matches with known teams, most recent first, e.g. 'Oct 15 18:00 · Cloud9 vs Karmine Corp'."""
        current = current.lower()
        choices = []
        for match_id, tournament, datetime_utc, best_of, team1, team2, *_ in reversed(self.db.get_full_matches()):
            if team1 in PLACEHOLDER_TEAMS or team2 in PLACEHOLDER_TEAMS:
                continue
            label = f"{datetime.strptime(datetime_utc, '%Y-%m-%d %H:%M:%S'):%b %d %H:%M} UTC · {team1} vs {team2} (Bo{best_of})"
            if current in label.lower():
                choices.append(app_commands.Choice(name=label[:100], value=match_id))
            if len(choices) == 25:
                break
        return choices

    def prediction_cog(self):
        return self.bot.get_cog('PredictionBot')

    @app_commands.command(name="setresult", description="Enter a match result by hand, e.g. when Leaguepedia is slow or wrong (bot owner only)")
    @app_commands.describe(match="The match", team1_score="Games won by the first team", team2_score="Games won by the second team")
    @app_commands.autocomplete(match=match_autocomplete)
    @app_commands.default_permissions(manage_guild=True)
    @owner_only()
    async def setresult(self, interaction: discord.Interaction, match: str, team1_score: app_commands.Range[int, 0, 3], team2_score: app_commands.Range[int, 0, 3]):
        details = self.db.get_match_details(match)
        if details is None:
            await interaction.response.send_message("Match not found, pick one from the list.", ephemeral=True)
            return
        best_of, team1, team2 = details[3], details[4], details[5]
        wins_needed = (best_of + 1) // 2 if best_of else None
        if team1_score == team2_score or (wins_needed and max(team1_score, team2_score) != wins_needed):
            await interaction.response.send_message(f"That isn't a valid Bo{best_of} result, the winner needs exactly {wins_needed} wins.", ephemeral=True)
            return

        winner = 1 if team1_score > team2_score else 2
        self.db.set_result_override(match, winner, team1_score, team2_score)
        print(f"{interaction.user.display_name} set the result of {team1} vs {team2} to {team1_score}-{team2_score}.")
        await interaction.response.defer(ephemeral=True)
        message = await self.prediction_cog().refresh_match_message(match)
        note = "" if message else " (the match message couldn't be updated, it may not have been posted)"
        await interaction.followup.send(
            f"Result saved: **{team1} {team1_score}-{team2_score} {team2}**{note}. It stays in place until `/clearresult`, even if Leaguepedia shows something else.",
            ephemeral=True
        )

    @app_commands.command(name="clearresult", description="Remove a result entered with /setresult and use Leaguepedia's again (bot owner only)")
    @app_commands.autocomplete(match=match_autocomplete)
    @app_commands.default_permissions(manage_guild=True)
    @owner_only()
    async def clearresult(self, interaction: discord.Interaction, match: str):
        if not self.db.clear_result_override(match):
            await interaction.response.send_message("That match has no manual result.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        # fetch leaguepedia's result again, then redraw the message
        cog = self.prediction_cog()
        await cog.run_cycle()
        await cog.refresh_match_message(match)
        await interaction.followup.send("Manual result removed, the match uses Leaguepedia's data again.", ephemeral=True)

    @app_commands.command(name="repost", description="Post a match's prediction message again, e.g. if it was deleted (bot owner only)")
    @app_commands.autocomplete(match=match_autocomplete)
    @app_commands.default_permissions(manage_guild=True)
    @owner_only()
    async def repost(self, interaction: discord.Interaction, match: str):
        if self.db.get_match_details(match) is None:
            await interaction.response.send_message("Match not found, pick one from the list.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        message = await self.prediction_cog().refresh_match_message(match, repost=True)
        await interaction.followup.send(f"Reposted: {message.jump_url}" if message else "Couldn't post the message, check CHANNEL_ID.", ephemeral=True)

    @app_commands.command(name="status", description="Bot health: last data update, errors, next match (bot owner only)")
    @app_commands.default_permissions(manage_guild=True)
    @owner_only()
    async def status(self, interaction: discord.Interaction):
        api = self.bot.api_handler
        now = datetime.now(timezone.utc)
        upcoming = self.db.get_upcoming_matches(now, now.replace(year=now.year + 1))
        next_match = next(((m[2], m[4], m[5]) for m in upcoming), None)
        next_text = f"{next_match[1]} vs {next_match[2]} {discord_time(next_match[0], 'R')}" if next_match else "none scheduled"

        lines = [
            f"**Mode:** {'TEST' if config.TEST_MODE else 'live'} · database `{config.DATABASE_NAME}`",
            f"**Running since:** {discord_time(self.bot.start_time, 'R')}",
            f"**Last Leaguepedia update:** {discord_time(api.last_success, 'R') if api.last_success else 'none yet'}",
        ]
        if api.last_error:
            lines.append(f"**Last error:** {discord_time(api.last_error[0], 'R')} — `{api.last_error[1]}`")
        lines += [
            f"**Next match:** {next_text}",
            f"**Matches:** {self.db.count('matches')} · **posted:** {self.db.count('posted_messages')} · **manual results:** {self.db.count('result_overrides')}",
            f"**Predictions:** {self.db.count('predictions')} · **bonus picks:** {self.db.count('bonus_picks')} · **reminders on:** {self.db.count('reminder_users')}",
            f"**Last backup:** {self.db.get_state('last_backup_date') or 'none yet'}",
        ]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Admin(bot))
