import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta
from typing import Optional
from tournament import BonusResults, score_bonus, format_bonus_picks, bonus_lock_time

def points_text(points):
    return f"{points} point{'' if points == 1 else 's'}"


# discord allows at most 4096 characters in an embed description, stay a bit below it
EMBED_DESCRIPTION_LIMIT = 4000


def score_prediction(best_of, actual_winner, team1_score, team2_score, predicted_winner, predicted_team1_score, predicted_team2_score):
    """Points for one prediction, or None if the match has no result yet."""
    if actual_winner not in (1, 2):
        return None
    if predicted_winner != actual_winner:
        return 0
    exact_score = predicted_team1_score == team1_score and predicted_team2_score == team2_score
    if best_of == 3 and exact_score:
        return 2
    if best_of == 5 and exact_score:
        return 3
    return 1


def calculate_scores(matches_data, predictions_data):
    matches = {match_id: (best_of, winner, team1_score, team2_score) for match_id, best_of, winner, team1_score, team2_score in matches_data}
    user_scores = {}

    for user_id, username, match_id, predicted_winner, predicted_team1_score, predicted_team2_score in predictions_data:
        if match_id not in matches:
            continue
        points = score_prediction(*matches[match_id], predicted_winner, predicted_team1_score, predicted_team2_score)
        if points is None:
            continue
        entry = user_scores.setdefault(user_id, {'username': username, 'score': 0, 'correct': 0, 'played': 0})
        entry['score'] += points
        entry['played'] += 1
        if points > 0:
            entry['correct'] += 1

    return user_scores


def chunk_lines(lines, limit=EMBED_DESCRIPTION_LIMIT):
    chunks, current = [], ""
    for line in lines:
        if current and len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = ""
        current += line + "\n"
    if current:
        chunks.append(current)
    return chunks


async def send_paged_embeds(ctx, title, lines, ephemeral=False, color=0x00ff00):
    chunks = chunk_lines(lines)
    for i, chunk in enumerate(chunks):
        page_title = title if len(chunks) == 1 else f"{title} ({i + 1}/{len(chunks)})"
        await ctx.send(embed=discord.Embed(title=page_title, description=chunk, color=color), ephemeral=ephemeral)


def discord_time(datetime_utc, style='f'):
    ts = int(datetime.strptime(datetime_utc, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp())
    return f"<t:{ts}:{style}>"


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
`/leaderboard` · `/predictions` · `/bonus` · `/schedule` · `/rules`
"""


class BotCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    # every command below is a hybrid command: it works both as /name and as !name

    @commands.command()
    async def all_commands(self, ctx):
        await ctx.send("All commands are available as slash commands now, type `/` to see them: `/leaderboard`, `/predictions`, `/bonus`, `/schedule`, `/rules`.")

    @commands.hybrid_command(description="Prediction rules and scoring")
    async def rules(self, ctx):
        await ctx.send(RULES_TEXT, ephemeral=True)

    @commands.hybrid_command(description="Current standings")
    async def leaderboard(self, ctx):
        user_scores = calculate_scores(self.db.get_all_matches(), self.db.get_all_predictions())

        # bonus points count towards the overall score
        bonus = score_bonus(self.db.get_bonus_picks(), BonusResults(self.db.get_full_matches()))
        for user_id, data in bonus.items():
            entry = user_scores.setdefault(user_id, {'username': data['username'], 'score': 0, 'correct': 0, 'played': 0})
            entry['score'] += data['points']
            entry['bonus'] = data['points']

        if not any(data['played'] or data.get('bonus') for data in user_scores.values()):
            await ctx.send("No results yet, the leaderboard will appear once the first predicted match is finished.")
            return

        sorted_scores = sorted(user_scores.values(), key=lambda x: x['score'], reverse=True)
        lines = []
        rank = 0
        previous_score = None
        for position, data in enumerate(sorted_scores, start=1):
            # tied users share a rank
            if data['score'] != previous_score:
                rank = position
                previous_score = data['score']
            bonus_text = f", {data['bonus']} from bonus" if data.get('bonus') else ""
            lines.append(f"**{rank}.** {data['username']} — {points_text(data['score'])} ({data['correct']}/{data['played']} correct{bonus_text})")

        await send_paged_embeds(ctx, "Leaderboard", lines)

    @commands.hybrid_command(aliases=["my_predictions"], description="Your predictions and points, or someone else's")
    async def predictions(self, ctx, user: Optional[discord.Member] = None):
        user = user or ctx.author
        predictions = self.db.get_user_predictions(user.id)
        bonus_picks = self.db.get_bonus_picks(user.id)
        if not predictions and not bonus_picks:
            await ctx.send(f"{'You have' if user == ctx.author else user.display_name + ' has'} no predictions recorded.", ephemeral=True)
            return

        lines = []
        total = 0

        if bonus_picks:
            matches = self.db.get_full_matches()
            lock_time = bonus_lock_time(matches)
            bonus_locked = lock_time is not None and datetime.now(timezone.utc) >= lock_time
            lines.append("__**Bonus predictions**__")
            if user != ctx.author and not bonus_locked:
                # other people's bonus picks stay hidden until the lock
                lines.append(f"Hidden until the swiss stage starts {discord_time(lock_time.strftime('%Y-%m-%d %H:%M:%S'), 'R')}." if lock_time else "Hidden for now.")
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
        await send_paged_embeds(ctx, f"{user.display_name}'s Predictions", lines, ephemeral=True)

    @commands.hybrid_command(description="Matches in the next 14 days")
    async def schedule(self, ctx):
        current_utc_time = datetime.now(timezone.utc)
        upcoming_matches = self.db.get_upcoming_matches(current_utc_time, current_utc_time + timedelta(days=14))
        if not upcoming_matches:
            await ctx.send("No upcoming matches found.", ephemeral=True)
            return

        lines = []
        for match_id, tournament, datetime_utc, best_of, team1, team2, winner, team1_score, team2_score in upcoming_matches:
            lines.append(f"{discord_time(datetime_utc)} — **{team1}** vs **{team2}** (Bo{best_of})")

        await send_paged_embeds(ctx, "Upcoming Matches", lines, ephemeral=True)


async def setup(bot):
    await bot.add_cog(BotCommands(bot))
