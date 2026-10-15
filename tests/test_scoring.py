"""
Run from the project folder with:  python -m unittest discover tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scoring import score_prediction, calculate_scores, rank_scores, user_stats
from match_message import picks_line
from tournament import BonusResults, score_bonus, bonus_lock_time, bonus_team_options, match_stage

P = "2026 Season World Championship/"


def match(page, team1, team2, winner=None, score=(None, None), best_of=1, time='2026-10-23 17:00:00'):
    return (P + page, 'Worlds 2026 Main Event', time, best_of, team1, team2, winner, score[0], score[1])


class MatchScoringTests(unittest.TestCase):
    def test_bo1(self):
        self.assertEqual(score_prediction(1, 1, 1, 0, 1, 1, 0), 1)
        self.assertEqual(score_prediction(1, 1, 1, 0, 2, 0, 1), 0)

    def test_bo3(self):
        self.assertEqual(score_prediction(3, 1, 2, 1, 1, 2, 1), 2)  # exact
        self.assertEqual(score_prediction(3, 1, 2, 1, 1, 2, 0), 1)  # winner only
        self.assertEqual(score_prediction(3, 1, 2, 1, 2, 1, 2), 0)  # wrong

    def test_bo5(self):
        self.assertEqual(score_prediction(5, 2, 1, 3, 2, 1, 3), 3)  # exact
        self.assertEqual(score_prediction(5, 2, 1, 3, 2, 0, 3), 1)  # winner only
        self.assertEqual(score_prediction(5, 2, 1, 3, 1, 3, 2), 0)  # wrong

    def test_unplayed_match_scores_nothing(self):
        self.assertIsNone(score_prediction(5, None, None, None, 1, 3, 0))

    def test_calculate_scores(self):
        matches = [('m1', 5, 1, 3, 1), ('m2', 1, 2, 0, 1), ('m3', 3, None, None, None)]
        predictions = [
            (1, 'Alice', 'm1', 1, 3, 1),  # exact bo5: 3
            (1, 'Alice', 'm2', 2, 0, 1),  # bo1: 1
            (1, 'Alice', 'm3', 1, 2, 0),  # not played yet
            (2, 'Bob', 'm1', 2, 2, 3),    # wrong: 0
        ]
        scores = calculate_scores(matches, predictions)
        self.assertEqual(scores[1]['score'], 4)
        self.assertEqual((scores[1]['correct'], scores[1]['played']), (2, 2))
        self.assertEqual(scores[2]['score'], 0)


class StandingsAndStatsTests(unittest.TestCase):
    def test_stage_filter(self):
        matches = [(P + 'Play-In_Round 1_1', 5, 1, 3, 0), (P + 'Main Event_Round 1_1', 1, 1, 1, 0)]
        predictions = [(1, 'Alice', P + 'Play-In_Round 1_1', 1, 3, 0), (1, 'Alice', P + 'Main Event_Round 1_1', 1, 1, 0)]
        self.assertEqual(calculate_scores(matches, predictions, 'Play-In')[1]['score'], 3)
        self.assertEqual(calculate_scores(matches, predictions, 'Swiss')[1]['score'], 1)
        self.assertNotIn(1, calculate_scores(matches, predictions, 'Knockouts'))

    def test_tied_users_share_rank(self):
        ranked = rank_scores({1: {'username': 'b', 'score': 5}, 2: {'username': 'a', 'score': 5}, 3: {'username': 'c', 'score': 2}})
        self.assertEqual([(e['username'], e['rank']) for e in ranked], [('a', 1), ('b', 1), ('c', 3)])

    def test_streaks_and_formats(self):
        def row(best_of, predicted, actual):
            # (match_id, best_of, team1, team2, predicted_winner, p1, p2, time, winner, s1, s2)
            return ('m', best_of, 'A', 'B', 1, predicted[0], predicted[1], '2026-10-23 17:00:00', 1 if actual[0] > actual[1] else 2, actual[0], actual[1])
        rows = [
            row(1, (1, 0), (1, 0)),  # correct
            row(3, (2, 0), (2, 0)),  # correct, exact
            row(5, (3, 1), (3, 2)),  # correct
            row(1, (1, 0), (0, 1)),  # wrong
            row(3, (2, 1), (2, 1)),  # correct, exact
        ]
        stats = user_stats(rows)
        self.assertEqual((stats['correct'], stats['played']), (4, 5))
        self.assertEqual((stats['best_streak'], stats['current_streak']), (3, 1))
        self.assertEqual(stats['exact'], 2)
        self.assertEqual(stats['by_format'][1], [1, 2])
        self.assertEqual(stats['points'], 1 + 2 + 1 + 0 + 2)


class PicksLineTests(unittest.TestCase):
    def test_grouped_in_button_order(self):
        line = picks_line([('Carl', 2, 1, 3), ('alice', 1, 3, 1), ('Bob', 1, 3, 1), ('Dana', 1, 3, 0)])
        self.assertEqual(line, "Picks: **3-0**: Dana · **3-1**: alice, Bob · **1-3**: Carl")

    def test_exact_score_marked_after_result(self):
        line = picks_line([('Alice', 1, 3, 1)], winner=1, team1_score=3, team2_score=1)
        self.assertIn("**3-1** ✅", line)

    def test_no_picks(self):
        self.assertEqual(picks_line([]), "Picks: none yet")


def swiss_and_knockouts():
    """A small made-up main event: A goes 3-0, H goes 0-3, B is eliminated in swiss, A beats C in the final."""
    return [
        match("Main Event_Round 1_1", 'A', 'H', winner=1, time='2026-10-23 17:00:00'),
        match("Main Event_Round 1_2", 'B', 'C', winner=2, time='2026-10-23 18:00:00'),
        match("Main Event_Round 2_1", 'A', 'B', winner=1),
        match("Main Event_Round 2_2", 'H', 'C', winner=2),
        match("Main Event_Round 3_1", 'A', 'C', winner=1),
        match("Main Event_Round 3_2", 'H', 'B', winner=2),
        match("Main Event_Round 4_1", 'B', 'D', winner=2),
        match("Main Event_Round 5_1", 'B', 'E', winner=2),
        match("Main Event_Semifinals_1", 'A', 'D', winner=1, best_of=5),
        match("Main Event_Finals_1", 'A', 'C', winner=1, score=(3, 2), best_of=5),
    ]


class BonusTests(unittest.TestCase):
    def test_match_stage(self):
        self.assertEqual(match_stage(P + "Play-In_Round 1_1"), 'Play-In')
        self.assertEqual(match_stage(P + "Main Event_Round 3_2"), 'Swiss')
        self.assertEqual(match_stage(P + "Main Event_Quarterfinals_1"), 'Knockouts')
        self.assertEqual(match_stage(P + "Main Event_Finals_1"), 'Knockouts')

    def test_lock_time_is_first_swiss_match(self):
        matches = [match("Play-In_Round 1_1", 'X', 'Y', time='2026-10-15 18:00:00')] + swiss_and_knockouts()
        self.assertEqual(bonus_lock_time(matches).strftime('%Y-%m-%d %H:%M'), '2026-10-23 17:00')

    def test_team_options_include_play_in_teams(self):
        options = bonus_team_options([('T1', 'Main Event'), ('Cloud9', 'Play-In'), ('Gen.G', 'Main Event')])
        self.assertEqual(options, ['Cloud9', 'Gen.G', 'T1'])

    def test_statuses_after_full_tournament(self):
        results = BonusResults(swiss_and_knockouts())
        self.assertTrue(results.status('swiss_3_0', 'A'))
        self.assertFalse(results.status('swiss_3_0', 'C'))
        self.assertTrue(results.status('swiss_0_3', 'H'))
        self.assertFalse(results.status('swiss_0_3', 'B'))  # B won a game
        self.assertTrue(results.status('finalist', 'C'))
        self.assertFalse(results.status('finalist', 'D'))
        self.assertTrue(results.status('winner', 'A'))
        self.assertFalse(results.status('winner', 'C'))

    def test_statuses_while_undecided(self):
        # only round 1 played: A 1-0, H 0-1
        results = BonusResults(swiss_and_knockouts()[:2] + [match("Main Event_Finals_1", 'TBD', 'TBD', best_of=5)])
        self.assertIsNone(results.status('swiss_3_0', 'A'))
        self.assertFalse(results.status('swiss_3_0', 'H'))
        self.assertIsNone(results.status('swiss_0_3', 'H'))
        self.assertIsNone(results.status('finalist', 'A'))
        self.assertIsNone(results.status('winner', 'H'))

    def test_eliminated_teams_are_wrong_early(self):
        # B lost 3 swiss games, so B can't be a finalist or winner even before the final is set
        matches = [m for m in swiss_and_knockouts() if 'Finals' not in m[0]] + [match("Main Event_Finals_1", 'TBD', 'TBD', best_of=5)]
        results = BonusResults(matches)
        self.assertFalse(results.status('finalist', 'B'))
        self.assertFalse(results.status('winner', 'B'))
        self.assertFalse(results.status('winner', 'D'))  # lost the semifinal
        self.assertIsNone(results.status('winner', 'A'))

    def test_play_in_team_that_did_not_qualify(self):
        # once the swiss draw is fully known, a team that isn't in it is wrong everywhere
        results = BonusResults(swiss_and_knockouts())
        self.assertFalse(results.status('swiss_3_0', 'Cloud9'))
        self.assertFalse(results.status('swiss_0_3', 'Cloud9'))
        self.assertFalse(results.status('winner', 'Cloud9'))

    def test_score_bonus_points(self):
        picks = [
            (1, 'Alice', 'winner', 'A'),       # 5
            (1, 'Alice', 'finalist', 'A'),     # 2
            (1, 'Alice', 'finalist', 'D'),     # 0
            (1, 'Alice', 'swiss_3_0', 'A'),    # 2
            (1, 'Alice', 'swiss_0_3', 'H'),    # 2
            (1, 'Alice', 'swiss_0_3', 'B'),    # 0
            (2, 'Bob', 'winner', 'C'),         # 0
        ]
        users = score_bonus(picks, BonusResults(swiss_and_knockouts()))
        self.assertEqual(users[1]['points'], 11)
        self.assertEqual(users[2]['points'], 0)


if __name__ == '__main__':
    unittest.main()
