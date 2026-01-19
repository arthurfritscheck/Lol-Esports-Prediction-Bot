# League Esports Prediction Discord Bot

A Discord bot that allows users to predict the outcomes and scores of professional League of Legends matches. It automatically fetches match schedules from Leaguepedia, handles user predictions via interactive buttons, and tracks scores on a leaderboard.

## Features

* **Automated Data Fetching**: Uses the `mwrogue` library to fetch match schedules and results directly from Leaguepedia (currently configured for Worlds 2024).
* **Interactive Predictions**: Users predict matches using Discord UI buttons (no complex typing required).
* **Dynamic Scoring System**: Points are awarded based on the match format (Best of 1, 3, or 5).
* **Leaderboard**: Tracks and displays user rankings based on prediction accuracy.
* **SQLite Database**: Automatically stores matches, user predictions, and results locally.

## Prerequisites

* Python 3.8+
* A Discord Bot Token
* A Discord Server (and the ID of the channel where predictions should appear)

## Installation

1. **Clone the repository** (or download the files):
```bash
git clone <https://github.com/arthurfritscheck/Lol-Esports-Prediction-Bot.git>
cd <Lol-Esports-Prediction-Bot>

```


2. **Install dependencies**:
```bash
pip install -r requirements.txt

```


3. **Environment Setup**:
Create a file named `.env` in the root directory. Add the following variables:
```env
DISCORD_TOKEN=your_discord_bot_token_here
DATABASE_NAME=matches.db
CHANNEL_ID=your_discord_channel_id_here

```


* `DISCORD_TOKEN`: Found in the Discord Developer Portal.
* `DATABASE_NAME`: You can name this whatever you like (e.g., `matches.db`).
* `CHANNEL_ID`: The ID of the text channel where the bot should post upcoming matches for users to vote on.


4. **Run the Bot**:
```bash
python main.py

```



## Usage

### Commands

Prefix: `!`

* `!rules`: Displays the scoring rules for predictions.
* `!schedule`: Shows the list of upcoming matches found in the database (next 14 days).
* `!leaderboard`: Displays the top users and their scores.
* `!my_predictions`: specific command to show the user their own prediction history.
* `!all_commands`: Lists all available commands.

### How it Works

1. **Fetching**: The bot checks Leaguepedia every 60 minutes for match updates.
2. **Posting**: When a new upcoming match is found, the bot posts a message in the configured `CHANNEL_ID` with buttons representing possible scores (e.g., "3-0", "3-1", etc.).
3. **Predicting**: Users click the button corresponding to their prediction.
* *Note: Predictions are locked once the match start time has passed.*


4. **Scoring**: After matches conclude and the bot updates its data, users can check the `!leaderboard` to see their points.

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



## Project Structure

* `main.py`: The entry point. Initializes the bot, database, and API handler.
* `API/api_client.py`: Handles communication with the Leaguepedia API via `mwrogue`.
* `callbacks/buttoncallback.py`: Logic for handling user interactions with prediction buttons.
* `cogs/`:
* `predictionbot.py`: Background task loop that checks for matches and posts them to the channel.
* `commands.py`: Handles chat commands like `!leaderboard` and `!rules`.
* `database/database.py`: Manages SQLite connections and table operations.

## Configuration Note

The specific tournaments being tracked are currently hardcoded in `API/api_client.py`. To change which tournaments the bot follows, edit the `tournament_names` list in the `update_match_data` function:

```python
# API/api_client.py
tournament_names = ["Worlds Qualifying Series 2024", 'Worlds 2024 Play-In', 'Worlds 2024 Main Event']

```

## Credits

* Data provided by [Leaguepedia](https://lol.fandom.com/wiki/League_of_Legends_Esports_Wiki) via the Cargo API.
* Built using `discord.py` and `mwrogue`.
