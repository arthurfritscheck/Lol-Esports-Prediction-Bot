import discord
from discord.ext import tasks, commands
from discord.ui import Button, View
from database.database import MatchDatabase
from callbacks.buttoncallback import button_callback
from datetime import datetime, timezone, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

class PredictionBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = MatchDatabase(os.getenv('DATABASE_NAME'))
        self.sent_matches = set()
        self.check_matches.start()

    @tasks.loop(minutes=60)
    async def check_matches(self):
        print("Checking for upcoming matches...")
        current_utc_time = datetime.now(timezone.utc)
        print(current_utc_time)

        upcoming_matches = self.db.get_upcoming_matches(current_utc_time, current_utc_time + timedelta(days=14))
        

        print(f"Found {len(upcoming_matches)} upcoming matches.")
        
        for match in upcoming_matches:
            print(match)
            match_id, tournament, datetime_utc, best_of, team1, team2, winner, team1_score, team2_score = match
            match_time = datetime.strptime(datetime_utc, '%Y-%m-%d %H:%M:%S')
            print(match_time)
            
            if match_id not in self.sent_matches:
                print(f"Match {match_id} between {team1} and {team2} is upcoming.")
                await self.send_prediction_message(match_id, best_of, team1, team2, match_time)
                self.sent_matches.add(match_id)

    async def send_prediction_message(self, match_id, best_of, team1, team2, match_time):
        view = View(timeout=None)
        # Create prediction buttons based on BestOf value (Bo1, Bo3, Bo5) 
        if best_of == 1:
            view.add_item(Button(label="1-0", style=discord.ButtonStyle.blurple, row=0, custom_id=f"predict${match_id}$1-0"))
            view.add_item(Button(label="0-1", style=discord.ButtonStyle.red, row=1, custom_id=f"predict${match_id}$0-1"))
        
        elif best_of == 3:
            view.add_item(Button(label="2-0", style=discord.ButtonStyle.blurple, row=0, custom_id=f"predict${match_id}$2-0"))
            view.add_item(Button(label="2-1", style=discord.ButtonStyle.blurple, row=0, custom_id=f"predict${match_id}$2-1"))
            view.add_item(Button(label="1-2", style=discord.ButtonStyle.red, row=1, custom_id=f"predict${match_id}$1-2"))
            view.add_item(Button(label="0-2", style=discord.ButtonStyle.red, row=1, custom_id=f"predict${match_id}$0-2"))
        
        elif best_of == 5:
            view.add_item(Button(label="3-0", style=discord.ButtonStyle.blurple, row=0, custom_id=f"predict${match_id}$3-0"))
            view.add_item(Button(label="3-1", style=discord.ButtonStyle.blurple, row=0, custom_id=f"predict${match_id}$3-1"))
            view.add_item(Button(label="3-2", style=discord.ButtonStyle.blurple, row=0, custom_id=f"predict${match_id}$3-2"))
            view.add_item(Button(label="0-3", style=discord.ButtonStyle.red, row=1, custom_id=f"predict${match_id}$0-3"))
            view.add_item(Button(label="1-3", style=discord.ButtonStyle.red, row=1, custom_id=f"predict${match_id}$1-3"))
            view.add_item(Button(label="2-3", style=discord.ButtonStyle.red, row=1, custom_id=f"predict${match_id}$2-3"))

        # Register the button callback
        for button in view.children:
            button.callback = button_callback
            print('Button callback registered')

        channel_id = int(os.getenv('CHANNEL_ID')) # convert string to int since discord channels are integers
        channel = self.bot.get_channel(channel_id)
        await channel.send(f"{team1} - {team2}\nBo{best_of}\n{match_time} UTC", view=view)


    @check_matches.before_loop
    async def before_check_matches(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(PredictionBot(bot))