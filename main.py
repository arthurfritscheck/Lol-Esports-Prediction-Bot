import discord
from discord import app_commands
from discord.ext import commands
from database.database import MatchDatabase
from API.api_client import APIHandler
from callbacks.buttoncallback import PredictButton
from datetime import datetime, timezone
import asyncio
import traceback
import config
from bot_logging import setup_logging
from checks import NotBotOwner

setup_logging(config.TEST_MODE)

# all commands are slash commands, so no privileged intents (like message content) are needed
intents = discord.Intents.default()

COGS = ['cogs.predictionbot', 'cogs.commands', 'cogs.bonus', 'cogs.admin', 'cogs.announcements']


class PredictionDiscordBot(commands.Bot):
    def __init__(self):
        # there are no text commands anymore, the prefix is only required by discord.py
        super().__init__(command_prefix=commands.when_mentioned, intents=intents, help_command=None)
        # one shared database connection for the whole bot
        self.db = MatchDatabase(config.DATABASE_NAME)
        self.db.create_tables()
        self.api_handler = APIHandler(self.db)
        self.commands_synced = False
        self.start_time = datetime.now(timezone.utc)

    async def setup_hook(self):
        # makes prediction buttons work on messages posted before a restart
        self.add_dynamic_items(PredictButton)
        for extension in COGS:
            await self.load_extension(extension)
        self.tree.on_error = on_app_command_error


bot = PredictionDiscordBot()


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}{" (TEST MODE)" if config.TEST_MODE else ""}')

    # on_ready fires again on every reconnect, so only sync once
    if not bot.commands_synced:
        bot.commands_synced = True
        # syncing per server makes slash commands show up instantly, global syncs can take up to an hour
        for guild in bot.guilds:
            bot.tree.copy_global_to(guild=guild)
            try:
                synced = await bot.tree.sync(guild=guild)
                print(f"Synced {len(synced)} slash commands to {guild.name}.")
            except discord.Forbidden:
                print(f"Could not add slash commands to {guild.name}: re-invite the bot with the 'applications.commands' scope "
                      f"(Developer Portal > OAuth2 > URL Generator, tick 'bot' and 'applications.commands').")


async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, NotBotOwner):
        message = "Only the bot owner can use this command."
    elif isinstance(error, app_commands.MissingPermissions):
        message = "You don't have permission to use this command."
    else:
        print(f"An error occurred in /{interaction.command.name if interaction.command else '?'}:")
        traceback.print_exception(type(error), error, error.__traceback__)
        message = "Something went wrong while running this command."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.HTTPException:
        pass


async def main():
    async with bot:
        await bot.start(config.DISCORD_TOKEN)

# run the bot
if __name__ == "__main__":
    asyncio.run(main())
