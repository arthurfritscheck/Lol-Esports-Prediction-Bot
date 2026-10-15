"""
Run from the project folder with:  python -m unittest discover tests
"""
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from API.polymarket import normalize_team, same_team, find_odds, series_markets
from match_message import odds_line

START = datetime(2026, 10, 15, 18, 0, tzinfo=timezone.utc)


class TeamNameTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize_team('LØS'), 'los')
        self.assertEqual(normalize_team('LYON (2024 American Team)'), 'lyon')
        self.assertEqual(normalize_team('FURIA Esports'), 'furia')
        self.assertEqual(normalize_team('Dplus KIA'), normalize_team('Dplus Kia'))

    def test_same_team(self):
        self.assertTrue(same_team('FURIA', 'FURIA Esports'))
        self.assertTrue(same_team('Gen.G', 'Gen.G Esports'))
        self.assertTrue(same_team('LØS', 'LOS'))
        self.assertFalse(same_team('T1', 'T1A'))  # short names must match exactly
        self.assertFalse(same_team('Cloud9', 'Karmine Corp'))


def market(outcomes, prices, start=START):
    return (start, outcomes, prices, 'slug')


class FindOddsTests(unittest.TestCase):
    def test_same_order(self):
        self.assertEqual(find_odds([market(['Cloud9', 'Karmine Corp'], [0.325, 0.675])], 'Cloud9', 'Karmine Corp', START), (33, 67, 'slug'))

    def test_swapped_order(self):
        self.assertEqual(find_odds([market(['Karmine Corp', 'Cloud9'], [0.675, 0.325])], 'Cloud9', 'Karmine Corp', START)[:2], (33, 67))

    def test_percentages_add_up_to_100(self):
        team1, team2, _ = find_odds([market(['A Team', 'B Team'], [0.51, 0.51])], 'A Team', 'B Team', START)
        self.assertEqual(team1 + team2, 100)

    def test_time_too_far_apart(self):
        self.assertIsNone(find_odds([market(['Cloud9', 'Karmine Corp'], [0.3, 0.7], START + timedelta(days=1))], 'Cloud9', 'Karmine Corp', START))

    def test_only_one_team_matches(self):
        self.assertIsNone(find_odds([market(['Cloud9', 'Team Liquid'], [0.3, 0.7])], 'Cloud9', 'Karmine Corp', START))

    def test_series_markets_only_uses_open_moneyline(self):
        events = [{'slug': 'x', 'markets': [
            {'sportsMarketType': 'child_moneyline', 'outcomes': '["A", "B"]', 'outcomePrices': '["0.4", "0.6"]', 'gameStartTime': '2026-10-15 18:00:00+00'},
            {'sportsMarketType': 'moneyline', 'outcomes': '["A", "B"]', 'outcomePrices': '["0.3", "0.7"]', 'gameStartTime': '2026-10-15 18:00:00+00'},
            {'sportsMarketType': 'moneyline', 'closed': True, 'outcomes': '["C", "D"]', 'outcomePrices': '["0.5", "0.5"]', 'gameStartTime': '2026-10-15 18:00:00+00'},
        ]}]
        markets = series_markets(events)
        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0][2], [0.3, 0.7])


class OddsLineTests(unittest.TestCase):
    def test_match_order(self):
        self.assertEqual(odds_line((32, 68, 'lol-c9-kc-2026-10-15', 0), 'Cloud9', 'Karmine Corp', 'open'),
                         "📈 [Polymarket](<https://polymarket.com/event/lol-c9-kc-2026-10-15>) odds: Cloud9 32% · Karmine Corp 68%")

    def test_closing_label_after_lock(self):
        self.assertIn("closing odds", odds_line((32, 68, 's', 1), 'Cloud9', 'Karmine Corp', 'locked'))
        self.assertNotIn("closing odds", odds_line((32, 68, 's', 1), 'Cloud9', 'Karmine Corp', 'open'))

    def test_no_odds(self):
        self.assertIsNone(odds_line(None, 'A', 'B', 'open'))


if __name__ == '__main__':
    unittest.main()
