import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone, timedelta
from typing import Literal, Optional
from tournament import BonusResults, score_bonus, format_bonus_picks, bonus_lock_time
from scoring import STAGES, score_prediction, build_standings, user_stats
from formatting import points_text, discord_time, respond_paged
from checks import is_bot_owner

RULES_TEXT = """
Predict the winner and the score for each match by clicking a button under its message. You can change your prediction until the match starts. Everyone can see who picked what on the match message.

**Scoring:**
- **Best of 1**: correct winner = 1 point
- **Best of 3**: correct winner = 1 point, correct winner & score = 2 points
- **Best of 5**: correct winner = 1 point, correct winner & score = 3 points

**Bonus predictions** (`/bonus`, lock when the swiss stage starts):
- Tournament winner = 5 points
- Each correct finalist = 2 points
- Each correct swiss 3-0 team = 2 points
- Each correct swiss 0-3 team = 2 points

**Commands:**
`/leaderboard` · `/predictions` · `/stats` · `/bonus` · `/schedule` · `/reminders` · `/rules`
"""


def leaderboard_lines(standings, stage=None):
    lines = []
    for entry in standings:
        bonus_text = f", {entry['bonus']} from bonus" if entry.get('bonus') else ""
        lines.append(f"**{entry['rank']}.** {entry['username']} — {points_text(entry['score'])} ({entry['correct']}/{entry['played']} correct{bonus_text})")
    return lines


def percent(correct, total):
    return f"{round(100 * correct / total)}%" if total else "—"


class BotCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    @app_commands.command(name="rules", description="Prediction rules and scoring")
    async def rules(self, interaction: discord.Interaction):
        await interaction.response.send_message(RULES_TEXT, ephemeral=True)

    @app_commands.command(name="leaderboard", description="Current standings, overall or for one stage")
    @app_commands.describe(stage="Only count matches of this stage (bonus points only count overall)")
    async def leaderboard(self, interaction: discord.Interaction, stage: Literal['Overall', 'Play-In', 'Swiss', 'Knockouts'] = 'Overall'):
        stage_filter = None if stage == 'Overall' else stage
        standings = build_standings(self.db, stage_filter)
        if not standings:
            message = "No results yet, the leaderboard will appear once the first predicted match is finished."
            if stage_filter:
                message = f"No {stage} results yet."
            await interaction.response.send_message(message, ephemeral=bool(stage_filter))
            return
        title = "Leaderboard" if stage == 'Overall' else f"Leaderboard — {stage}"
        await respond_paged(interaction, title, leaderboard_lines(standings))

    @app_commands.command(name="predictions", description="Your predictions and points, or someone else's")
    @app_commands.describe(user="Whose predictions to show (default: yours)")
    async def predictions(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        user = user or interaction.user
        is_self = user.id == interaction.user.id
        predictions = self.db.get_user_predictions(user.id)
        bonus_picks = self.db.get_bonus_picks(user.id)
        if not predictions and not bonus_picks:
            await interaction.response.send_message(f"{'You have' if is_self else user.display_name + ' has'} no predictions recorded.", ephemeral=True)
            return

        lines = []
        total = 0

        if bonus_picks:
            matches = self.db.get_full_matches()
            lock_time = bonus_lock_time(matches)
            bonus_locked = lock_time is not None and datetime.now(timezone.utc) >= lock_time
            lines.append("__**Bonus predictions**__")
            if not is_self and not bonus_locked:
                # other people's bonus picks stay hidden until the lock
                lines.append(f"Hidden until the swiss stage starts {discord_time(lock_time, 'R')}." if lock_time else "Hidden for now.")
            else:
                bonus = score_bonus(bonus_picks, BonusResults(matches)).get(user.id)
                lines += format_bonus_picks(bonus['picks'])
                lines.append(f"Bonus points: {bonus['points']}")
                total += bonus['points']
            lines.append("\n__**Matches**__")
            if not predictions:
                lines.append("No match predictions yet.")

        for (match_id, best_of, team1, team2, predicted_winner, predicted_team1_score, predicted_team2_score,
             datetime_utc, winner, team1_score, team2_score) in predictions:
            predicted_winner_team_name = team1 if predicted_winner == 1 else team2
            points = score_prediction(best_of, winner, team1_score, team2_score, predicted_winner, predicted_team1_score, predicted_team2_score)

            if points is None:
                result = "⏳"
            else:
                total += points
                result = f"{'✅' if points > 0 else '❌'} {team1_score}-{team2_score}, +{points}"

            when = discord_time(datetime_utc, 'd') if datetime_utc else ""
            lines.append(f"{when} **{team1}** vs **{team2}** (Bo{best_of}): {predicted_winner_team_name} {predicted_team1_score}-{predicted_team2_score} — {result}")

        lines.append(f"\n**Total: {points_text(total)}**")
        await respond_paged(interaction, f"{user.display_name}'s Predictions", lines, ephemeral=True)

    @app_commands.command(name="stats", description="Accuracy, exact scores and streaks, yours or someone else's")
    @app_commands.describe(user="Whose stats to show (default: yours)")
    async def stats(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        user = user or interaction.user
        stats = user_stats(self.db.get_user_predictions(user.id))
        standings = build_standings(self.db)
        entry = next((e for e in standings if e['user_id'] == user.id), None)

        if stats['played'] == 0 and entry is None:
            await interaction.response.send_message(f"{'You have' if user.id == interaction.user.id else user.display_name + ' has'} no finished predictions yet.", ephemeral=True)
            return

        format_lines = []
        for best_of, (correct, total) in stats['by_format'].items():
            if total:
                format_lines.append(f"Bo{best_of}: {correct}/{total} ({percent(correct, total)})")

        lines = [
            f"**Rank:** {entry['rank']} of {len(standings)}" if entry else "**Rank:** —",
            f"**Points:** {entry['score'] if entry else 0}" + (f" ({entry['bonus']} from bonus)" if entry and entry.get('bonus') else ""),
            f"**Correct winners:** {stats['correct']}/{stats['played']} ({percent(stats['correct'], stats['played'])})",
            f"**By format:** {' · '.join(format_lines) if format_lines else '—'}",
            f"**Exact scores** (Bo3/Bo5): {stats['exact']}",
            f"**Current streak:** {stats['current_streak']} · **Best streak:** {stats['best_streak']}",
        ]
        await respond_paged(interaction, f"{user.display_name}'s Stats", lines, ephemeral=True)

    @app_commands.command(name="schedule", description="Matches in the next 14 days")
    async def schedule(self, interaction: discord.Interaction):
        current_utc_time = datetime.now(timezone.utc)
        upcoming_matches = self.db.get_upcoming_matches(current_utc_time, current_utc_time + timedelta(days=14))
        if not upcoming_matches:
            await interaction.response.send_message("No upcoming matches found.", ephemeral=True)
            return

        lines = []
        for match_id, tournament, datetime_utc, best_of, team1, team2, winner, team1_score, team2_score in upcoming_matches:
            lines.append(f"{discord_time(datetime_utc)} — **{team1}** vs **{team2}** (Bo{best_of})")

        await respond_paged(interaction, "Upcoming Matches", lines, ephemeral=True)

    @app_commands.command(name="reminders", description="Get pinged an hour before matches you haven't predicted yet")
    @app_commands.describe(setting="Turn reminders on or off, or list who gets them",
                           user="Bot owner only: change the setting for someone else")
    async def reminders(self, interaction: discord.Interaction, setting: Literal['on', 'off', 'list'], user: Optional[discord.Member] = None):
        if setting == 'list':
            user_ids = self.db.get_reminder_users()
            names = ", ".join(f"<@{user_id}>" for user_id in user_ids) or "nobody yet"
            await interaction.response.send_message(f"Reminders are on for: {names}", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
            return

        target = user or interaction.user
        if target.id != interaction.user.id and not await is_bot_owner(interaction.user, interaction.client):
            await interaction.response.send_message("Only the bot owner can change reminders for someone else.", ephemeral=True)
            return

        self.db.set_reminder(target.id, setting == 'on')
        who = "You" if target.id == interaction.user.id else target.display_name
        if setting == 'on':
            message = f"{who} will be pinged about an hour before each match that hasn't been predicted yet."
        else:
            message = f"{who} won't get reminder pings anymore."
        await interaction.response.send_message(message, ephemeral=True)


async def setup(bot):
    await bot.add_cog(BotCommands(bot))
