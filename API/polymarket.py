import json
import re
import unicodedata
from datetime import datetime, timezone, timedelta
import aiohttp
import config

GAMMA_EVENTS_URL = "https://gamma-api.polymarket.com/events"

# polymarket and leaguepedia start times can differ a little if a match gets moved
MAX_TIME_DIFFERENCE = timedelta(hours=3)
# words that one site includes in a team name and the other doesn't, e.g. 'FURIA Esports' vs 'FURIA'
FILLER_WORDS = {'esports', 'esport', 'gaming', 'team', 'club', 'the'}


def normalize_team(name):
    """'LØS' -> 'los', 'LYON (2024 American Team)' -> 'lyon', 'FURIA Esports' -> 'furia', 'Dplus KIA' -> 'dpluskia'"""
    name = re.sub(r'\(.*?\)', '', name or '').lower().replace('ø', 'o')
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    words = [w for w in re.findall(r'[a-z0-9]+', name) if w not in FILLER_WORDS]
    return ''.join(words)


def same_team(leaguepedia_name, polymarket_name):
    a, b = normalize_team(leaguepedia_name), normalize_team(polymarket_name)
    if not a or not b:
        return False
    # also covers names where one site adds a sponsor or city, e.g. 'Gen.G' vs 'Gen.G Esports'
    return a == b or (min(len(a), len(b)) >= 3 and (a.startswith(b) or b.startswith(a)))


def parse_market_time(value):
    # e.g. '2026-10-15 18:00:00+00'
    try:
        return datetime.strptime(value[:19], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def series_markets(events):
    """The 'Match Winner' market of every match event: (start time, [outcome names], [prices], event slug)."""
    markets = []
    for event in events:
        for market in event.get('markets', []):
            if market.get('sportsMarketType') != 'moneyline' or market.get('closed'):
                continue
            try:
                outcomes = json.loads(market['outcomes'])
                prices = [float(p) for p in json.loads(market['outcomePrices'])]
            except (KeyError, TypeError, ValueError):
                continue
            start = parse_market_time(market.get('gameStartTime'))
            if len(outcomes) == 2 and len(prices) == 2 and start is not None:
                markets.append((start, outcomes, prices, event.get('slug')))
    return markets


def find_odds(markets, team1, team2, match_time):
    """Win chances in percent as (team1, team2, slug), or None if there's no confident match."""
    for start, outcomes, prices, slug in markets:
        if abs(start - match_time) > MAX_TIME_DIFFERENCE:
            continue
        if same_team(team1, outcomes[0]) and same_team(team2, outcomes[1]):
            price1, price2 = prices
        elif same_team(team1, outcomes[1]) and same_team(team2, outcomes[0]):
            price2, price1 = prices
        else:
            continue
        if price1 + price2 <= 0:
            return None
        # prices are roughly probabilities, normalise so the two always add up to 100
        # round half up (32.5 -> 33) like people expect, python's round() would give 32
        team1_percent = int(100 * price1 / (price1 + price2) + 0.5)
        return team1_percent, 100 - team1_percent, slug
    return None


async def fetch_series_markets():
    """All open match-winner markets of the tournament tag, or [] if polymarket can't be reached."""
    events = []
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for offset in range(0, 1000, 100):
            params = {'tag_slug': config.POLYMARKET_TAG, 'closed': 'false', 'limit': '100', 'offset': str(offset)}
            async with session.get(GAMMA_EVENTS_URL, params=params) as response:
                response.raise_for_status()
                page = await response.json()
            events += page
            if len(page) < 100:
                break
    return series_markets(events)
