import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta

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


async def send_paged_embeds(ctx, title, lines, color=0x00ff00):
    chunks = chunk_lines(lines)
    for i, chunk in enumerate(chunks):
        page_title = title if len(chunks) == 1 else f"{title} ({i + 1}/{len(chunks)})"
        await ctx.send(embed=discord.Embed(title=page_title, description=chunk, color=color))


def discord_time(datetime_utc, style='f'):
    ts = int(datetime.strptime(datetime_utc, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp())
    return f"<t:{ts}:{style}>"


class BotCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    @commands.command()
    async def all_commands(self, ctx):
        await ctx.send("""
List of commands:
!rules
!schedule
!leaderboard
!my_predictions
!refresh (admins only)
""")

    @commands.command()
    async def rules(self, ctx):
        rules_text = """
Predict the winner and the score for each match by clicking a button under its message. You can change your prediction until the match starts.

**Prediction Rules:**

Scoring:
- **Best of 1**: correct winner = 1 point
- **Best of 3**: correct winner = 1 point, correct winner & score = 2 points
- **Best of 5**: correct winner = 1 point, correct winner & score = 3 points
"""
        await ctx.send(rules_text)

    @commands.command()
    async def leaderboard(self, ctx):
        user_scores = calculate_scores(self.db.get_all_matches(), self.db.get_all_predictions())
        if not user_scores:
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
            lines.append(f"**{rank}.** {data['username']} — {data['score']} points ({data['correct']}/{data['played']} correct)")

        await send_paged_embeds(ctx, "Leaderboard", lines)

    @commands.command()
    async def my_predictions(self, ctx):
        predictions = self.db.get_user_predictions(ctx.author.id)
        if not predictions:
            await ctx.send("You have no predictions recorded.")
            return

        lines = []
        total = 0
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

        lines.append(f"\n**Total: {total} points**")
        await send_paged_embeds(ctx, f"{ctx.author.display_name}'s Predictions", lines)

    @commands.command()
    async def schedule(self, ctx):
        current_utc_time = datetime.now(timezone.utc)
        upcoming_matches = self.db.get_upcoming_matches(current_utc_time, current_utc_time + timedelta(days=14))
        if not upcoming_matches:
            await ctx.send("No upcoming matches found.")
            return

        lines = []
        for match_id, tournament, datetime_utc, best_of, team1, team2, winner, team1_score, team2_score in upcoming_matches:
            lines.append(f"{discord_time(datetime_utc)} — **{team1}** vs **{team2}** (Bo{best_of})")

        await send_paged_embeds(ctx, "Upcoming Matches", lines)


async def setup(bot):
    await bot.add_cog(BotCommands(bot))
