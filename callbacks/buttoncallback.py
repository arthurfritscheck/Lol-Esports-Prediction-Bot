from datetime import datetime, timezone
from database.database import MatchDatabase
import discord
import os
from dotenv import load_dotenv

load_dotenv()

db = MatchDatabase(os.getenv('DATABASE_NAME'))

async def button_callback(interaction: discord.Interaction):
    try:
        user_id = interaction.user.id
        username = interaction.user.display_name
        username_mention = interaction.user.mention
        custom_id = interaction.data['custom_id']
        custom_id_parts = custom_id.split("$")
        match_id = custom_id_parts[1]
        prediction = "-".join(custom_id_parts[2:])

        # parse prediction
        predicted_team1_score, predicted_team2_score = map(int, prediction.split("-"))

        # get match details
        match_details = db.get_match_details(match_id)

        if not match_details:
            await interaction.response.send_message("Match details not found!", ephemeral=True)
            return
        
        # extract match details
        tournament = match_details[1]
        match_time_str = match_details[2]
        best_of, team1, team2 = match_details[3], match_details[4], match_details[5]
        match_time = datetime.strptime(match_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)

        # check if match has started
        current_time = datetime.now(timezone.utc)
        if current_time > match_time:
            await interaction.response.send_message("This match has already started, you cannot predict anymore.", ephemeral=True)
            return

        # determine predicted winner based on scores (1 = team1 wins, 2 = team2 wins) for ease of comparison with leaguepedia's data
        predicted_winner = 1 if predicted_team1_score > predicted_team2_score else 2

        # store prediction in database
        db.store_prediction(user_id, username, match_id, tournament, match_time_str, best_of, team1, team2, predicted_winner, predicted_team1_score, predicted_team2_score)
        await interaction.response.send_message(f"{username_mention} predicted {predicted_team1_score}-{predicted_team2_score} for {team1}-{team2}.")
        
        print(f"{username} predicted {predicted_team1_score}-{predicted_team2_score} for {team1}-{team2}.")
    
    except Exception as e:
        print(f"An error occurred: {e}")
        await interaction.response.send_message("An error occurred while processing your prediction. Please try again later.", ephemeral=True)