import discord
from discord import app_commands
import config


class NotBotOwner(app_commands.CheckFailure):
    pass


async def is_bot_owner(user, client):
    # OWNER_IDS in .env wins, otherwise the owner of the bot application in the developer portal
    if config.OWNER_IDS:
        return user.id in config.OWNER_IDS
    return await client.is_owner(user)


def owner_only():
    """Only the bot owner may run the command, even other server admins can't."""
    async def predicate(interaction: discord.Interaction):
        if not await is_bot_owner(interaction.user, interaction.client):
            raise NotBotOwner()
        return True
    return app_commands.check(predicate)
