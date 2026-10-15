from match_message import parse_match_time

PLACEHOLDER_TEAMS = {None, '', 'TBD'}

# category key -> label, number of teams to pick, points per correct team
BONUS_CATEGORIES = {
    'winner': {'label': 'Tournament winner', 'picks': 1, 'points': 5},
    'finalist': {'label': 'Finalists', 'picks': 2, 'points': 2},
    'swiss_3_0': {'label': 'Swiss 3-0', 'picks': 2, 'points': 2},
    'swiss_0_3': {'label': 'Swiss 0-3', 'picks': 2, 'points': 2},
}


def match_stage(match_id):
    """'2026 Season World Championship/Main Event_Round 1_1' -> 'Swiss', '.../Play-In_Round 1_1' -> 'Play-In', '.../Main Event_Finals_1' -> 'Knockouts'"""
    page = match_id.split('/', 1)[-1]
    if page.startswith('Play-In'):
        return 'Play-In'
    if page.startswith('Main Event_Round'):
        return 'Swiss'
    if page.startswith('Main Event'):
        return 'Knockouts'
    return 'Other'


def is_finals(match_id):
    return match_id.split('/', 1)[-1].startswith('Main Event_Finals')


def bonus_lock_time(matches):
    """Bonus picks lock when the first swiss match starts. None if the swiss schedule isn't known yet."""
    times = [parse_match_time(m[2]) for m in matches if match_stage(m[0]) == 'Swiss' and m[2]]
    return min(times) if times else None


def bonus_team_options(teams):
    """Every team that can still reach the main event: main event teams plus play-in teams (some of which qualify)."""
    return sorted({team for team, stage in teams if stage in ('Main Event', 'Play-In')}, key=str.lower)


class BonusResults:
    """Works out from the match data which bonus picks are correct (True), wrong (False) or not decided yet (None)."""

    def __init__(self, matches):
        self.records = {}
        self.knockout_losers = set()
        self.swiss_teams = set()
        self.finalists = None
        self.champion = None
        swiss_slots = 0

        for match_id, tournament, datetime_utc, best_of, team1, team2, winner, team1_score, team2_score in matches:
            stage = match_stage(match_id)
            if stage == 'Swiss':
                swiss_slots += 2
                for team in (team1, team2):
                    if team not in PLACEHOLDER_TEAMS:
                        self.swiss_teams.add(team)
                if winner in (1, 2):
                    winning_team, losing_team = (team1, team2) if winner == 1 else (team2, team1)
                    self.records.setdefault(winning_team, [0, 0])[0] += 1
                    self.records.setdefault(losing_team, [0, 0])[1] += 1
            elif stage == 'Knockouts':
                if winner in (1, 2):
                    self.knockout_losers.add(team2 if winner == 1 else team1)
                if is_finals(match_id):
                    if team1 not in PLACEHOLDER_TEAMS and team2 not in PLACEHOLDER_TEAMS:
                        self.finalists = {team1, team2}
                    if winner in (1, 2):
                        self.champion = team1 if winner == 1 else team2

        # once every team of the first swiss round is known (16 teams), anyone missing didn't qualify
        round_1 = [m for m in matches if m[0].split('/', 1)[-1].startswith('Main Event_Round 1_')]
        self.swiss_draw_known = bool(round_1) and all(m[4] not in PLACEHOLDER_TEAMS and m[5] not in PLACEHOLDER_TEAMS for m in round_1)

    def record(self, team):
        wins, losses = self.records.get(team, [0, 0])
        return wins, losses

    def is_eliminated(self, team):
        if self.swiss_draw_known and team not in self.swiss_teams:
            return True
        return self.record(team)[1] >= 3 or team in self.knockout_losers

    def status(self, category, team):
        wins, losses = self.record(team)
        not_qualified = self.swiss_draw_known and team not in self.swiss_teams

        if category == 'swiss_3_0':
            if wins == 3 and losses == 0:
                return True
            return False if losses > 0 or not_qualified else None
        if category == 'swiss_0_3':
            if losses == 3 and wins == 0:
                return True
            return False if wins > 0 or not_qualified else None
        if category == 'finalist':
            if self.finalists is not None:
                return team in self.finalists
            return False if self.is_eliminated(team) else None
        if category == 'winner':
            if self.champion is not None:
                return team == self.champion
            return False if self.is_eliminated(team) else None
        return None


def status_icon(status):
    return {True: '✅', False: '❌', None: '⏳'}[status]


def score_bonus(bonus_picks, results):
    """bonus_picks: rows of (user_id, username, category, team). Returns {user_id: {'username', 'points', 'picks': {category: [(team, status)]}}}"""
    users = {}
    for user_id, username, category, team in bonus_picks:
        if category not in BONUS_CATEGORIES:
            continue
        entry = users.setdefault(user_id, {'username': username, 'points': 0, 'picks': {}})
        status = results.status(category, team)
        entry['picks'].setdefault(category, []).append((team, status))
        if status is True:
            entry['points'] += BONUS_CATEGORIES[category]['points']
    return users


def format_bonus_picks(picks, show_status=True):
    """One line per category, e.g. 'Finalists: T1 ✅, Gen.G ⏳'"""
    lines = []
    for category, info in BONUS_CATEGORIES.items():
        entries = picks.get(category, [])
        if entries:
            teams = ', '.join(f"{team} {status_icon(status)}" if show_status else team for team, status in sorted(entries))
        else:
            teams = '—'
        lines.append(f"**{info['label']}**: {teams}")
    return lines
