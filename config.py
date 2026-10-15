import os
import sys
from dotenv import load_dotenv

# run with --test (or run_test_bot.bat) to use .env.test (test bot, test channel, test database) instead of .env
TEST_MODE = '--test' in sys.argv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env.test' if TEST_MODE else '.env'))

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
DATABASE_NAME = os.getenv('DATABASE_NAME', 'data/worldspredictions2026.db')

# leaguepedia bot password (Special:BotPasswords), username looks like "Name@BotName"
LEAGUEPEDIA_USERNAME = os.getenv('LEAGUEPEDIA_USERNAME')
LEAGUEPEDIA_PASSWORD = os.getenv('LEAGUEPEDIA_PASSWORD')

# every match whose leaguepedia overview page starts with this prefix is tracked (play-in, swiss, knockouts, ...)
TOURNAMENT_PAGE_PREFIX = os.getenv('TOURNAMENT_PAGE_PREFIX', '2026 Season World Championship/')

# how often match data is refreshed from leaguepedia
UPDATE_INTERVAL_MINUTES = int(os.getenv('UPDATE_INTERVAL_MINUTES', '10'))

# how far ahead prediction messages are posted
POST_WINDOW_DAYS = int(os.getenv('POST_WINDOW_DAYS', '6'))

# how long before a match opted-in users who haven't predicted get pinged
REMINDER_MINUTES = int(os.getenv('REMINDER_MINUTES', '60'))

# discord user ids allowed to use the admin commands, comma separated. Empty = the owner of the bot application
OWNER_IDS = {int(x) for x in os.getenv('OWNER_IDS', '').replace(' ', '').split(',') if x}

# polymarket odds on the match messages. POLYMARKET_TAG is the tag of the tournament's events on polymarket
POLYMARKET_ENABLED = os.getenv('POLYMARKET_ENABLED', 'true').lower() == 'true'
POLYMARKET_TAG = os.getenv('POLYMARKET_TAG', 'lol-worlds-2026')
