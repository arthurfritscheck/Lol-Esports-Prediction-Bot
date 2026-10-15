from datetime import datetime, timezone
import discord

# discord allows at most 4096 characters in an embed description, stay a bit below it
EMBED_DESCRIPTION_LIMIT = 4000


def points_text(points):
    return f"{points} point{'' if points == 1 else 's'}"


def discord_time(value, style='f'):
    """value: a 'YYYY-MM-DD HH:MM:SS' utc string or an aware datetime. Discord shows it in every user's own timezone."""
    if isinstance(value, str):
        value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
    return f"<t:{int(value.timestamp())}:{style}>"


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


def paged_embeds(title, lines, color=0x00ff00):
    chunks = chunk_lines(lines) or ["—"]
    return [discord.Embed(title=title if len(chunks) == 1 else f"{title} ({i + 1}/{len(chunks)})", description=chunk, color=color)
            for i, chunk in enumerate(chunks)]


async def respond_paged(interaction, title, lines, ephemeral=False, color=0x00ff00):
    """Answers a slash command with as many embeds as needed (discord allows 10 per message)."""
    embeds = paged_embeds(title, lines, color)
    for i in range(0, len(embeds), 10):
        if i == 0 and not interaction.response.is_done():
            await interaction.response.send_message(embeds=embeds[i:i + 10], ephemeral=ephemeral)
        else:
            await interaction.followup.send(embeds=embeds[i:i + 10], ephemeral=ephemeral)
