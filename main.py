import discord
from discord.ext import commands
from database.database import MatchDatabase
from API.api_client import APIHandler
import asyncio
import os
from dotenv import load_dotenv
import sqlite3

load_dotenv()

# initialize the bot with required intents
intents = discord.Intents.all()
intents.message_content = True  # ensure bot has necessary permissions

# specify intended prefix for commands
bot = commands.Bot(command_prefix="!", intents=intents)

# initialize database
db = MatchDatabase(os.getenv('DATABASE_NAME'))
db.create_tables()

# initialize API handler
api_handler = APIHandler(os.getenv('DATABASE_NAME'))
api_handler.update_match_data()

conn = sqlite3.connect(os.getenv('DATABASE_NAME'))
bot.db_cursor = conn.cursor()

# load cogs
cog_extensions = [
    'cogs.predictionbot',
    'cogs.commands'
]

async def load_extensions():
    for extension in cog_extensions:
        await bot.load_extension(extension)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command not found.")
    else:
        raise error

async def main():
    await load_extensions()
    await bot.start(os.getenv('DISCORD_TOKEN'))

# run the bot
if __name__ == "__main__":
    asyncio.run(main())