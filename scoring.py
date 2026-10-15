from tournament import BonusResults, score_bonus, match_stage

STAGES = ['Play-In', 'Swiss', 'Knockouts']


def score_prediction(best_of, actual_winner, team1_score, team2_score, predicted_winner, predicted_team1_score, predicted_team2_score):
    """Points for one prediction, or None if the match has no result yet."""
    if actual_winner not in (1, 2):
        return None
    if predicted_winner != actual_winner:
        return 0
    exact_score = predicted_team1_score == team1_score and predicted_team2_score == team2_score
    if best_of == 3 and exact_score:
        return 2
    if best_of == 5 and exact_score:
        return 3
    return 1


def calculate_scores(matches_data, predictions_data, stage=None):
    """matches_data: (MatchId, BestOf, Winner, Team1Score, Team2Score) rows. stage: only count matches of this stage, e.g. 'Swiss'."""
    matches = {match_id: (best_of, winner, team1_score, team2_score) for match_id, best_of, winner, team1_score, team2_score in matches_data
               if stage is None or match_stage(match_id) == stage}
    user_scores = {}

    for user_id, username, match_id, predicted_winner, predicted_team1_score, predicted_team2_score in predictions_data:
        if match_id not in matches:
            continue
        points = score_prediction(*matches[match_id], predicted_winner, predicted_team1_score, predicted_team2_score)
        if points is None:
            continue
        entry = user_scores.setdefault(user_id, {'username': username, 'score': 0, 'correct': 0, 'played': 0, 'bonus': 0})
        entry['score'] += points
        entry['played'] += 1
        if points > 0:
            entry['correct'] += 1

    return user_scores


def rank_scores(user_scores):
    """Sorted list of entries with 'user_id' and 'rank' added. Tied users share a rank."""
    entries = [dict(data, user_id=user_id) for user_id, data in user_scores.items()]
    entries.sort(key=lambda d: (-d['score'], d['username'].lower()))
    rank, previous_score = 0, None
    for position, entry in enumerate(entries, start=1):
        if entry['score'] != previous_score:
            rank, previous_score = position, entry['score']
        entry['rank'] = rank
    return entries


def build_standings(db, stage=None):
    """Ranked standings. The overall standings (stage=None) include bonus points."""
    user_scores = calculate_scores(db.get_all_matches(), db.get_all_predictions(), stage)
    if stage is None:
        bonus = score_bonus(db.get_bonus_picks(), BonusResults(db.get_full_matches()))
        for user_id, data in bonus.items():
            entry = user_scores.setdefault(user_id, {'username': data['username'], 'score': 0, 'correct': 0, 'played': 0, 'bonus': 0})
            entry['score'] += data['points']
            entry['bonus'] = data['points']
    # people who only made bonus picks that haven't scored yet don't need a leaderboard line
    user_scores = {user_id: data for user_id, data in user_scores.items() if data['played'] or data['bonus']}
    return rank_scores(user_scores)


def user_stats(user_predictions):
    """
    user_predictions: rows from db.get_user_predictions (ordered by match time).
    Returns accuracy per format, exact scores and streaks of correct winners.
    """
    stats = {'played': 0, 'correct': 0, 'points': 0, 'exact': 0, 'current_streak': 0, 'best_streak': 0,
             'by_format': {1: [0, 0], 3: [0, 0], 5: [0, 0]}}
    streak = 0
    for (match_id, best_of, team1, team2, predicted_winner, p1, p2, datetime_utc, winner, team1_score, team2_score) in user_predictions:
        points = score_prediction(best_of, winner, team1_score, team2_score, predicted_winner, p1, p2)
        if points is None:
            continue
        correct = points > 0
        stats['played'] += 1
        stats['points'] += points
        if best_of in stats['by_format']:
            stats['by_format'][best_of][1] += 1
            stats['by_format'][best_of][0] += correct
        if correct:
            stats['correct'] += 1
            streak += 1
            stats['best_streak'] = max(stats['best_streak'], streak)
        else:
            streak = 0
        if best_of in (3, 5) and p1 == team1_score and p2 == team2_score:
            stats['exact'] += 1
    stats['current_streak'] = streak
    return stats
