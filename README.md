# League-Esports-Prediction-Discord-Bot
A discord bot for the prediction of outcomes of professional League of Legends matches.

Match data comes from [Leaguepedia](https://lol.fandom.com). The bot posts a message with score buttons for every upcoming match, locks predictions when the match starts, and posts the result once it is known.

## Scoring
- **Best of 1**: correct winner = 1 point
- **Best of 3**: correct winner = 1 point, correct winner & score = 2 points
- **Best of 5**: correct winner = 1 point, correct winner & score = 3 points

## Commands
- `!rules`: prediction rules and scoring
- `!schedule`: matches in the next 14 days
- `!leaderboard`: current standings
- `!my_predictions`: your predictions and points
- `!refresh`: fetch match data right now (requires Manage Server)
- `!all_commands`: list of commands

## Setup
1. Install Python 3.9+ and the requirements:
   ```
   pip install -r requirements.txt
   ```
2. Create a Discord bot in the [Developer Portal](https://discord.com/developers/applications), enable the **Message Content** intent, and invite it with the View Channel, Send Messages, Embed Links and Read Message History permissions.
3. Create a Leaguepedia bot password at [Special:BotPasswords](https://lol.fandom.com/wiki/Special:BotPasswords). Read access is enough. Anonymous access is heavily rate limited.
4. Copy `.env.example` to `.env` and fill in the values.

## Running
Double-click `run_bot.bat` (Windows), which restarts the bot automatically if it crashes, or run:
```
python main.py
```

## Configuration
All settings are in `.env`:

| Variable | Description |
| --- | --- |
| `DISCORD_TOKEN` | Discord bot token |
| `CHANNEL_ID` | Channel where prediction messages are posted |
| `DATABASE_NAME` | Path to the SQLite database, e.g. `data/worldspredictions2026.db` |
| `LEAGUEPEDIA_USERNAME` / `LEAGUEPEDIA_PASSWORD` | Leaguepedia bot password login |
| `TOURNAMENT_PAGE_PREFIX` | Leaguepedia page prefix of the tracked tournament, default `2026 Season World Championship/` |
| `UPDATE_INTERVAL_MINUTES` | How often match data is refreshed, default `10` |
| `POST_WINDOW_DAYS` | How far ahead prediction messages are posted, default `6` |

To track a different tournament (e.g. next year's Worlds), change `TOURNAMENT_PAGE_PREFIX` and point `DATABASE_NAME` to a new database file.
