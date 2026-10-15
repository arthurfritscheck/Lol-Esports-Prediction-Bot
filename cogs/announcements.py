import json
import os
import discord
from discord.ext import tasks, commands
from datetime import datetime, timezone, timedelta
from match_message import parse_match_time
from scoring import build_standings
from formatting import discord_time, points_text, paged_embeds
import config

PLACEHOLDER_TEAMS = {None, '', 'TBD'}

# a match day is over when no match is waiting for its result and the next match is at least this far away
DAY_BREAK = timedelta(hours=4)
# matches that started longer ago than this without a result are ignored (e.g. a decider that was never needed)
RESULT_WAIT_LIMIT = timedelta(hours=12)
BACKUPS_TO_KEEP = 14


def rank_change_text(old_rank, new_rank):
    if old_rank is None:
        return "🆕"
    if new_rank < old_rank:
        return f"↑{old_rank - new_rank}"
    if new_rank > old_rank:
        return f"↓{new_rank - old_rank}"
    return "–"


class Announcements(commands.Cog):
    """Background jobs: reminder pings, the daily leaderboard post and the daily database backup."""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    async def cog_load(self):
        self.loop.start()

    async def cog_unload(self):
        self.loop.cancel()

    @tasks.loop(minutes=5)
    async def loop(self):
        now = datetime.now(timezone.utc)
        channel = self.bot.get_channel(config.CHANNEL_ID)
        # each job on its own, so one failing doesn't stop the others
        for job in (self.send_reminders, self.post_daily_leaderboard):
            if channel is None:
                break
            try:
                await job(channel, now)
            except Exception as e:
                print(f"An error occurred in {job.__name__}: {type(e).__name__}: {e}")
        try:
            self.backup_database(now)
        except Exception as e:
            print(f"An error occurred while backing up the database: {type(e).__name__}: {e}")

    @loop.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()

    async def send_reminders(self, channel, now):
        reminder_users = set(self.db.get_reminder_users())
        if not reminder_users:
            return

        lines = []
        to_ping = set()
        for match_id, channel_id, message_id, datetime_utc, team1, team2 in self.db.get_open_posted_matches():
            start = parse_match_time(datetime_utc)
            if not now < start <= now + timedelta(minutes=config.REMINDER_MINUTES):
                continue
            key = f"reminded:{match_id}"
            if self.db.get_state(key):
                continue
            self.db.set_state(key, now.isoformat())

            missing = reminder_users - self.db.get_predicted_user_ids(match_id)
            if not missing:
                continue
            to_ping |= missing
            link = f"https://discord.com/channels/{channel.guild.id}/{channel_id}/{message_id}"
            lines.append(f"**{team1}** vs **{team2}** {discord_time(start, 'R')}: {' '.join(f'<@{u}>' for u in sorted(missing))} — [predict here]({link})")

        if lines:
            await channel.send("⏰ **Reminder, you haven't predicted these yet:**\n" + "\n".join(lines),
                               allowed_mentions=discord.AllowedMentions(users=[discord.Object(u) for u in to_ping]))
            print(f"Sent reminders for {len(lines)} match(es).")

    async def post_daily_leaderboard(self, channel, now):
        matches = self.db.get_full_matches()
        finished = [m for m in matches if m[6] in (1, 2)]
        if not finished:
            return

        # wait while a match is being played or its result isn't in yet
        for match_id, tournament, datetime_utc, best_of, team1, team2, winner, *_ in matches:
            if winner in (1, 2) or team1 in PLACEHOLDER_TEAMS or team2 in PLACEHOLDER_TEAMS:
                continue
            if now - RESULT_WAIT_LIMIT <= parse_match_time(datetime_utc) <= now:
                return

        # and until the day's last match is done, i.e. the next match is far enough away
        upcoming = [parse_match_time(m[2]) for m in matches if parse_match_time(m[2]) > now]
        if upcoming and min(upcoming) - now < DAY_BREAK:
            return

        previous = json.loads(self.db.get_state('daily_leaderboard') or '{}')
        if len(finished) <= previous.get('finished', 0):
            return

        standings = build_standings(self.db)
        old_ranks = previous.get('ranks', {})
        old_scores = previous.get('scores', {})
        lines = []
        for entry in standings:
            key = str(entry['user_id'])
            gained = entry['score'] - old_scores.get(key, 0)
            change = rank_change_text(old_ranks.get(key), entry['rank']) if previous else ""
            gained_text = f" ({gained:+d} today)" if gained and previous else ""
            lines.append(f"**{entry['rank']}.** {entry['username']} — {points_text(entry['score'])}{gained_text} {change}".rstrip())

        if lines:
            new_results = len(finished) - previous.get('finished', 0)
            title = f"📊 Leaderboard — {new_results} new result{'' if new_results == 1 else 's'}"
            for embed in paged_embeds(title, lines, color=0x3498db):
                await channel.send(embed=embed)
            print("Posted the daily leaderboard.")

        self.db.set_state('daily_leaderboard', json.dumps({
            'finished': len(finished),
            'ranks': {str(e['user_id']): e['rank'] for e in standings},
            'scores': {str(e['user_id']): e['score'] for e in standings},
        }))

    def backup_database(self, now):
        today = now.strftime('%Y-%m-%d')
        if self.db.get_state('last_backup_date') == today:
            return
        db_path = os.path.abspath(config.DATABASE_NAME)
        backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        name = os.path.splitext(os.path.basename(db_path))[0]
        self.db.backup_to(os.path.join(backup_dir, f"{name}-{today}.db"))
        self.db.set_state('last_backup_date', today)

        # only keep the newest backups of this database
        backups = sorted(f for f in os.listdir(backup_dir) if f.startswith(name + '-') and f.endswith('.db'))
        for old in backups[:-BACKUPS_TO_KEEP]:
            os.remove(os.path.join(backup_dir, old))
        print(f"Backed up the database to {backup_dir}.")


async def setup(bot):
    await bot.add_cog(Announcements(bot))
