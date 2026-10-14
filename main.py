import discord
from discord.ext import commands
from database.database import MatchDatabase
from API.api_client import APIHandler
from callbacks.buttoncallback import PredictButton
import asyncio
import sys
import config

# the windows console can't print emoji in usernames by default, which would crash the print calls
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# only message content is needed for the ! commands, no privileged member/presence intents
intents = discord.Intents.default()
intents.message_content = True


class PredictionDiscordBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        # one shared database connection for the whole bot
        self.db = MatchDatabase(config.DATABASE_NAME)
        self.db.create_tables()
        self.api_handler = APIHandler(self.db)

    async def setup_hook(self):
        # makes prediction buttons work on messages posted before a restart
        self.add_dynamic_items(PredictButton)
        for extension in ['cogs.predictionbot', 'cogs.commands']:
            await self.load_extension(extension)


bot = PredictionDiscordBot()


@bot.event
async def on_ready():
    # on_ready fires again on every reconnect, so nothing in here should start tasks
    print(f'Logged in as {bot.user}')


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command not found. Use !all_commands to see the list.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.")
    else:
        raise error


async def main():
    async with bot:
        await bot.start(config.DISCORD_TOKEN)

# run the bot
if __name__ == "__main__":
    asyncio.run(main())
