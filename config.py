import os
from dotenv import load_dotenv

load_dotenv()

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
