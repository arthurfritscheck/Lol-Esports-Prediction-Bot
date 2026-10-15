# League Esports Prediction Discord Bot

A Discord bot that allows users to predict the outcomes and scores of professional League of Legends matches. It automatically fetches match schedules from Leaguepedia, handles user predictions via interactive buttons, and tracks scores on a leaderboard.

## Features

* **Automated Data Fetching**: Uses the `mwrogue` library to fetch match schedules and results directly from Leaguepedia (currently configured for Worlds 2026).
* **Interactive Predictions**: Users predict matches using Discord UI buttons (no complex typing required). Buttons keep working after a bot restart.
* **Automatic Locking & Results**: Buttons are disabled when a match starts, and the match message is updated with the result and how many users predicted it correctly.
* **Local Times**: Match times use Discord timestamps, so every user sees them in their own timezone with a countdown.
* **Dynamic Scoring System**: Points are awarded based on the match format (Best of 1, 3, or 5).
* **Leaderboard**: Tracks and displays user rankings based on prediction accuracy.
* **SQLite Database**: Automatically stores matches, user predictions, posted messages, and results locally.

## Prerequisites

* Python 3.9+
* A Discord Bot Token, with the **Message Content** intent enabled in the Developer Portal
* A Discord Server (and the ID of the channel where predictions should appear)
* A Leaguepedia bot password (anonymous access to Leaguepedia is heavily rate limited)

## Installation

1. **Clone the repository** (or download the files):
```bash
git clone https://github.com/arthurfritscheck/League-Esports-Prediction-Discord-Bot.git
cd League-Esports-Prediction-Discord-Bot
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Leaguepedia login**:
Create a bot password at [Special:BotPasswords](https://lol.fandom.com/wiki/Special:BotPasswords) while logged in to your Fandom account. Read access is enough. The username it gives you looks like `YourName@BotName`.

4. **Environment Setup**:
Copy `.env.example` to `.env` in the root directory and fill in the values:
```env
DISCORD_TOKEN=your_discord_bot_token_here
CHANNEL_ID=your_discord_channel_id_here
DATABASE_NAME=data/worldspredictions2026.db
LEAGUEPEDIA_USERNAME=YourName@BotName
LEAGUEPEDIA_PASSWORD=your_bot_password_here
```

* `DISCORD_TOKEN`: Found in the Discord Developer Portal.
* `CHANNEL_ID`: The ID of the text channel where the bot should post upcoming matches for users to vote on.
* `DATABASE_NAME`: You can name this whatever you like. Use a new file for every tournament.
* `LEAGUEPEDIA_USERNAME` / `LEAGUEPEDIA_PASSWORD`: The bot password from step 3.

Optional settings:

| Variable | Default | Description |
| --- | --- | --- |
| `TOURNAMENT_PAGE_PREFIX` | `2026 Season World Championship/` | Leaguepedia page prefix of the tracked tournament |
| `UPDATE_INTERVAL_MINUTES` | `10` | How often match data is refreshed |
| `POST_WINDOW_DAYS` | `6` | How far ahead prediction messages are posted |

5. **Run the Bot**:
On Windows, double-click `run_bot.bat`, which restarts the bot automatically if it crashes. Or run:
```bash
python main.py
```

6. **Test bot (optional)**:
To try changes without affecting the real server, put a second bot's token, a test channel and a test database in `.env.test`, and start it with `run_test_bot.bat` (or `python main.py --test`). It can run at the same time as the real bot.

## Usage

### Commands

All commands are slash commands (the old `!` versions still work for now). Replies marked *private* are only visible to the user who ran the command.

* `/rules`: Displays the scoring rules for predictions (private).
* `/schedule`: Shows the list of upcoming matches (next 14 days, private).
* `/leaderboard`: Displays the top users and their scores.
* `/predictions [user]`: Shows your own prediction history and points, or another user's (private).
* `/bonus`: Make or change your bonus predictions (private). After the lock, shows everyone's bonus picks.
* `/refresh`: Fetches match data right now (requires the Manage Server permission, private).

The bot must be invited with the `bot` and `applications.commands` scopes for slash commands to appear.

### How it Works

1. **Fetching**: The bot checks Leaguepedia every 10 minutes for new matches, reschedules, and results.
2. **Posting**: When an upcoming match has both teams decided, the bot posts a message in the configured `CHANNEL_ID` with buttons representing possible scores (e.g., "3-0", "3-1", etc.).
3. **Predicting**: Users click the button corresponding to their prediction, and can change it until the match starts. The confirmation is only visible to the user, and the match message shows a live list of who picked what.
4. **Locking**: Once the match starts, the buttons are disabled.
5. **Scoring**: After the match concludes, the message shows the result, and users can check the `!leaderboard` to see their points.

## Scoring System

Points are awarded based on the accuracy of the prediction and the length of the series:

* **Best of 1 (Bo1)**:
  * Correct Winner: **1 point**
* **Best of 3 (Bo3)**:
  * Correct Winner (only): **1 point**
  * Correct Winner + Correct Score (Exact Prediction): **2 points**
* **Best of 5 (Bo5)**:
  * Correct Winner (only): **1 point**
  * Correct Winner + Correct Score (Exact Prediction): **3 points**

### Bonus Predictions

Before the swiss stage starts, everyone can use `/bonus` to predict:

* The tournament winner: **5 points**
* The two finalists: **2 points** each
* The two teams that go 3-0 in swiss: **2 points** each
* The two teams that go 0-3 in swiss: **2 points** each

Picks are hidden until they lock when the first swiss match starts, then the bot posts everyone's picks. Results are worked out automatically from the match data and count towards the leaderboard.

## Logs and Tests

* Everything the bot prints is also written to `logs/bot.log` (or `logs/test-bot.log` for the test bot).
* Run the scoring tests with `python -m unittest discover tests`.

## Project Structure

* `main.py`: The entry point. Initializes the bot, database, and API handler.
* `config.py`: Loads all settings from `.env`.
* `API/api_client.py`: Handles communication with the Leaguepedia API via `mwrogue`.
* `callbacks/buttoncallback.py`: The persistent prediction buttons and the logic for handling clicks.
* `match_message.py`: Builds the text of a match message (header, picks, lock notice, result).
* `tournament.py`: Tournament stages and bonus prediction grading.
* `bot_logging.py`: Log file and console setup.
* `cogs/bonus.py`: The `/bonus` command and the bonus announcements.
* `tests/`: Unit tests for the scoring.
* `cogs/`:
  * `predictionbot.py`: Background task loop that refreshes match data, posts matches, locks them, and posts results.
  * `commands.py`: Handles chat commands like `!leaderboard` and `!rules`, and the scoring logic.
* `database/database.py`: Manages the SQLite connection and table operations.
* `run_bot.bat`: Windows launcher that restarts the bot if it stops.
* `run_test_bot.bat`: Windows launcher for the test bot (`.env.test`).

## Tracking a Different Tournament

The tracked tournament is set by `TOURNAMENT_PAGE_PREFIX` in `.env`. Every match on Leaguepedia whose overview page starts with this prefix is tracked (play-in, group/swiss stage, and knockouts). For next year's Worlds, change it to e.g. `2027 Season World Championship/` and point `DATABASE_NAME` to a new database file.

## Credits

* Data provided by [Leaguepedia](https://lol.fandom.com/wiki/League_of_Legends_Esports_Wiki) via the Cargo API.
* Built using `discord.py` and `mwrogue`.
