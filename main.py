import discord
from discord.ext import commands
from database.database import MatchDatabase
from API.api_client import APIHandler
from callbacks.buttoncallback import PredictButton
import asyncio
import traceback
import config
from bot_logging import setup_logging

setup_logging(config.TEST_MODE)

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
        self.commands_synced = False

    async def setup_hook(self):
        # makes prediction buttons work on messages posted before a restart
        self.add_dynamic_items(PredictButton)
        for extension in ['cogs.predictionbot', 'cogs.commands', 'cogs.bonus']:
            await self.load_extension(extension)


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


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command not found. Type `/` to see the available commands.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.", ephemeral=True)
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"Invalid input: {error}", ephemeral=True)
    else:
        print(f"An error occurred in command {ctx.command}:")
        traceback.print_exception(type(error), error, error.__traceback__)
        await ctx.send("Something went wrong while running this command.", ephemeral=True)


async def main():
    async with bot:
        await bot.start(config.DISCORD_TOKEN)

# run the bot
if __name__ == "__main__":
    asyncio.run(main())
