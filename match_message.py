from datetime import datetime, timezone


def parse_match_time(datetime_utc):
    return datetime.strptime(datetime_utc, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)


def spoiler(text):
    # team names and results are hidden behind discord spoilers (click to reveal), for people watching later
    return f"||{text}||"


def match_header(team1, team2, best_of, tournament, match_time):
    # discord timestamps render in each user's own timezone, :R shows a live countdown
    ts = int(match_time.timestamp())
    return f"{spoiler(f'**{team1}** vs **{team2}**')}\nBo{best_of} · {tournament}\n<t:{ts}:F> (<t:{ts}:R>)"


def mention(user_id):
    # shows as the user's clickable @name; the bot's default allowed_mentions makes sure this never pings
    return f"<@{user_id}>"


def picks_line(predictions, winner=None, team1_score=None, team2_score=None):
    """
    Who picked what, grouped by score, e.g. '3-1: @Alice, @Bob · 1-3: @Carl'. Scores are from team1's perspective, like the buttons.
    predictions: rows of (user_id, username, predicted_winner, team1_score, team2_score)
    """
    if not predictions:
        return "Picks: none yet"

    by_score = {}
    for user_id, username, predicted_winner, p1, p2 in predictions:
        by_score.setdefault((p1, p2), []).append((username, user_id))

    # team1 wins first (3-0, 3-1, ...), then team2 wins (2-3, 1-3, ...), same order as the buttons
    order = sorted(by_score, key=lambda s: (s[0] < s[1], -s[0], s[1]))
    groups = []
    for p1, p2 in order:
        mark = f" {spoiler('✅')}" if winner in (1, 2) and (p1, p2) == (team1_score, team2_score) else ""
        users = sorted(by_score[(p1, p2)], key=lambda u: u[0].lower())
        groups.append(f"**{p1}-{p2}**{mark}: {', '.join(mention(user_id) for _, user_id in users)}")
    return "Picks: " + " · ".join(groups)


def result_summary(predictions, team1, team2, winner, team1_score, team2_score):
    correct_winner = sum(1 for _, _, predicted_winner, _, _ in predictions if predicted_winner == winner)
    exact = sum(1 for _, _, _, p1, p2 in predictions if p1 == team1_score and p2 == team2_score)

    winner_name = team1 if winner == 1 else team2
    # winner's score first, e.g. 'Karmine Corp won 3-1'
    score = f" {max(team1_score, team2_score)}-{min(team1_score, team2_score)}" if team1_score is not None and team2_score is not None else ""
    return (f"✅ {spoiler(f'**{winner_name}** won{score}.')}\n"
            f"{correct_winner}/{len(predictions)} predicted the winner, {exact} got the exact score.")


def odds_line(odds, team1, team2, state):
    """e.g. '📈 Polymarket odds: ||Cloud9 32% · Karmine Corp 68%||', in the same order as the match"""
    if not odds:
        return None
    team1_percent, team2_percent, slug, closing = odds
    label = "closing odds" if closing and state != 'open' else "odds"
    # <...> around the url stops discord from adding a big link preview under every match message
    source = f"[Polymarket](<https://polymarket.com/event/{slug}>)" if slug else "Polymarket"
    return f"📈 {source} {label}: {spoiler(f'{team1} {team1_percent}% · {team2} {team2_percent}%')}"


def render_match_message(db, match_id, state):
    """Full content of a match's prediction message for the given state: 'open', 'locked' or 'final'."""
    match_id, tournament, datetime_utc, best_of, team1, team2, winner, team1_score, team2_score = db.get_match_details(match_id)
    predictions = db.get_match_predictions(match_id)

    content = match_header(team1, team2, best_of, tournament, parse_match_time(datetime_utc))
    odds = odds_line(db.get_market_odds(match_id), team1, team2, state)
    if odds:
        content += "\n" + odds
    content += "\n" + picks_line(predictions, winner if state == 'final' else None, team1_score, team2_score)
    if state == 'locked':
        content += "\n🔒 Predictions are closed."
    elif state == 'final':
        content += "\n" + result_summary(predictions, team1, team2, winner, team1_score, team2_score)
    return content
