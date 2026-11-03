import time
import discord
from discord.ext import commands
from checks import is_bot_owner
import config

# how long the "predictions only" notice stays visible, and how often one user can trigger it
NOTICE_SECONDS = 8
NOTICE_COOLDOWN_SECONDS = 60


class ChannelGuard(commands.Cog):
    """
    Keeps the prediction channel free of chat: regular messages are deleted, only the bot owner can post.
    Slash commands and button clicks aren't messages, so they keep working.
    Needs the Manage Messages permission in the prediction channel.
    """

    def __init__(self, bot):
        self.bot = bot
        self.last_notice = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not config.CHANNEL_GUARD_ENABLED or message.channel.id != config.CHANNEL_ID:
            return
        if message.author.id == self.bot.user.id or await is_bot_owner(message.author, self.bot):
            return

        try:
            await message.delete()
        except discord.Forbidden:
            print("Can't delete messages in the prediction channel, give the bot the Manage Messages permission there.")
            return
        except discord.NotFound:
            return

        # a short notice, at most once a minute per user so it can't be used to spam the channel
        now = time.monotonic()
        if now - self.last_notice.get(message.author.id, 0) < NOTICE_COOLDOWN_SECONDS:
            return
        self.last_notice[message.author.id] = now
        where = f" Chat about the games in <#{config.DISCUSSION_CHANNEL_ID}>." if config.DISCUSSION_CHANNEL_ID else ""
        try:
            await message.channel.send(
                f"{message.author.mention} this channel is for predictions only, use the buttons and `/` commands.{where}",
                delete_after=NOTICE_SECONDS,
                allowed_mentions=discord.AllowedMentions(users=[message.author])
            )
        except discord.HTTPException:
            pass


async def setup(bot):
    await bot.add_cog(ChannelGuard(bot))
