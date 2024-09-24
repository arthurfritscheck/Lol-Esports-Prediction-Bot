import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta
from database.database import MatchDatabase
import os
from dotenv import load_dotenv

load_dotenv()


class BotCommands(commands.Cog):
    def __init__(self, bot, db_cursor):
        self.bot = bot
        self.db_cursor = db_cursor
        self.db = MatchDatabase(os.getenv('DATABASE_NAME'))


    @commands.command()
    async def all_commands(self, ctx):
        await ctx.send("""
List of commands:
!rules
!schedule
!leaderboard
!my_predictions
""")

    @commands.command()
    async def leaderboard(self, ctx):
        user_scores = self.calculate_scores()
        embed = self.create_leaderboard_embed(user_scores)
        await ctx.send(embed=embed)

    @commands.command()
    async def rules(self, ctx):
        rules_text = """
Predict the winner and the score for each match.

**Prediction Rules:**

Scoring:
- **Best of 1**: correct winner = 1 point
- **Best of 3**: correct winner = 1 point, correct winner & score = 2 points
- **Best of 5**: correct winner = 1 point, correct winner & score = 3 points
"""
        await ctx.send(rules_text)

    def calculate_scores(self):
        user_scores = {}

        self.db_cursor.execute("SELECT MatchId, BestOf, Winner, Team1Score, Team2Score FROM matches")
        matches_data = self.db_cursor.fetchall()

        self.db_cursor.execute("SELECT UserID, Username, MatchId, PredictedWinner, PredictedTeam1Score, PredictedTeam2Score FROM predictions")
        predictions_data = self.db_cursor.fetchall()

        for user_id, username, predicted_match_id, predicted_winner, predicted_team1_score, predicted_team2_score in predictions_data:
            # find the actual match data for the predicted match
            for match_id, best_of, actual_winner, team1_score, team2_score in matches_data:
                if predicted_match_id == match_id:
                    # ensure match is played and data is available
                    if actual_winner is not None and team1_score is not None and team2_score is not None:
                        if user_id not in user_scores:
                            user_scores[user_id] = {'username': username, 'score': 0}

                        # scoring logic based on best of format (1, 3, 5)
                        if best_of == 1:
                            if predicted_winner == actual_winner:
                                user_scores[user_id]['score'] += 1
                        elif best_of == 3:
                            if predicted_winner == actual_winner and predicted_team1_score == team1_score and predicted_team2_score == team2_score:
                                user_scores[user_id]['score'] += 2
                            elif predicted_winner == actual_winner:
                                user_scores[user_id]['score'] += 1
                        elif best_of == 5:
                            if predicted_winner == actual_winner and predicted_team1_score == team1_score and predicted_team2_score == team2_score:
                                user_scores[user_id]['score'] += 3
                            elif predicted_winner == actual_winner:
                                user_scores[user_id]['score'] += 1

        return user_scores

    def create_leaderboard_embed(self, user_scores):
        embed = discord.Embed(title="leaderboard", color=0x00ff00)
        sorted_scores = sorted(user_scores.items(), key=lambda x: x[1]['score'], reverse=True)

        user_field = ""
        score_field = ""

        for user_id, data in sorted_scores:
            user_field += f"{data['username']}\n"
            score_field += f"{data['score']} points\n"

        embed.add_field(name="User", value=user_field, inline=True)
        embed.add_field(name="Score", value=score_field, inline=True)

        return embed
    
    @commands.command()
    async def my_predictions(self, ctx):
        user_id = ctx.author.id
        self.db_cursor.execute("SELECT MatchId, BestOf, Team1, Team2, PredictedWinner, PredictedTeam1Score, PredictedTeam2Score FROM predictions WHERE UserID = ?", (user_id,))
        predictions = self.db_cursor.fetchall()
        
        if predictions:
            embed = discord.Embed(title=f"{ctx.author.name}'s Predictions", color=0x00ff00)
            for pred in predictions:
                match_id, best_of, team1, team2, predicted_winner, predicted_team1_score, predicted_team2_score = pred
                predicted_winner_team_name = team1 if predicted_winner == team1 else team2
                embed.add_field(name=f"Match ID: {match_id}, Best of: {best_of}", value=f"Team1: {team1} - Team2: {team2}\nPredicted Winner: {predicted_winner_team_name}\nPredicted Score: {predicted_team1_score}-{predicted_team2_score}", inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send("You have no predictions recorded.")

    @commands.command()
    async def schedule(self, ctx):
        current_utc_time = datetime.now(timezone.utc)
        upcoming_matches = self.db.get_upcoming_matches(current_utc_time, current_utc_time + timedelta(days=14))
        embed = discord.Embed(title="Upcoming Matches", color=0x00ff00)
        if upcoming_matches:
            for match in upcoming_matches:
                match_id, tournament, datetime_utc, best_of, team1, team2, winner, team1_score, team2_score = match
                match_time = datetime.strptime(datetime_utc, '%Y-%m-%d %H:%M:%S')
                embed.add_field(name=f"Match ID: {match_id}, Best of: {best_of}", value=f"Tournament: {tournament}\n{team1} vs {team2}\nMatch Time: {match_time}", inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send("No upcoming matches found.")

async def setup(bot):
    db_cursor = bot.db_cursor
    await bot.add_cog(BotCommands(bot, db_cursor))