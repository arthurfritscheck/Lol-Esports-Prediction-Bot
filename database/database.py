import os
import sqlite3


class MatchDatabase:
    def __init__(self, db_path):
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def create_tables(self):
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS matches (
            MatchId TEXT PRIMARY KEY,
            Tournament TEXT,
            DateTime_UTC TEXT,
            BestOf INTEGER,
            Team1 TEXT,
            Team2 TEXT,
            Winner INTEGER,
            Team1Score INTEGER,
            Team2Score INTEGER
        )''')

        self.cursor.execute('''CREATE TABLE IF NOT EXISTS predictions (
                UserID INTEGER,
                Username TEXT,
                MatchId TEXT,
                Tournament TEXT,
                DateTime_UTC DATETIME,
                BestOf INTEGER,
                Team1 TEXT,
                Team2 TEXT,
                PredictedWinner INTEGER,
                PredictedTeam1Score INTEGER,
                PredictedTeam2Score INTEGER,
                PRIMARY KEY (UserID, MatchId)
            )''')

        # one row per prediction message posted in discord, so restarts don't repost and messages can be edited later
        # State: 'open' (accepting predictions), 'locked' (match started), 'final' (result posted)
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS posted_messages (
                MatchId TEXT PRIMARY KEY,
                ChannelId INTEGER,
                MessageId INTEGER,
                State TEXT
            )''')

        # teams taking part, from leaguepedia's tournament rosters (Stage is e.g. 'Play-In' or 'Main Event')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS teams (
                Team TEXT,
                Stage TEXT,
                PRIMARY KEY (Team, Stage)
            )''')

        # bonus predictions, one row per picked team, e.g. (user, 'finalist', 'T1')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS bonus_picks (
                UserID INTEGER,
                Username TEXT,
                Category TEXT,
                Team TEXT,
                PRIMARY KEY (UserID, Category, Team)
            )''')

        # small key/value store for one-off events, e.g. whether the bonus picks were already announced
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS bot_state (
                Key TEXT PRIMARY KEY,
                Value TEXT
            )''')

        # results entered by an admin with /setresult, they win over leaguepedia's data until cleared
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS result_overrides (
                MatchId TEXT PRIMARY KEY,
                Winner INTEGER,
                Team1Score INTEGER,
                Team2Score INTEGER
            )''')

        # polymarket win chances per match. Closing = 1 once the odds right before the start are stored
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS market_odds (
                MatchId TEXT PRIMARY KEY,
                Team1Percent INTEGER,
                Team2Percent INTEGER,
                Slug TEXT,
                Closing INTEGER,
                FetchedAt TEXT
            )''')

        # users who opted in to reminder pings
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS reminder_users (
                UserID INTEGER PRIMARY KEY
            )''')

        self.conn.commit()

    def set_result_override(self, match_id, winner, team1_score, team2_score):
        self.cursor.execute("""
            INSERT INTO result_overrides (MatchId, Winner, Team1Score, Team2Score) VALUES (?, ?, ?, ?)
            ON CONFLICT(MatchId) DO UPDATE SET Winner = excluded.Winner, Team1Score = excluded.Team1Score, Team2Score = excluded.Team2Score
        """, (match_id, winner, team1_score, team2_score))
        self.conn.commit()
        self.apply_result_overrides()

    def clear_result_override(self, match_id):
        self.cursor.execute("DELETE FROM result_overrides WHERE MatchId=?", (match_id,))
        removed = self.cursor.rowcount > 0
        self.conn.commit()
        return removed

    def apply_result_overrides(self):
        """Called after every leaguepedia update, so manual results don't get overwritten."""
        self.cursor.execute("""
            UPDATE matches SET
                Winner = (SELECT Winner FROM result_overrides o WHERE o.MatchId = matches.MatchId),
                Team1Score = (SELECT Team1Score FROM result_overrides o WHERE o.MatchId = matches.MatchId),
                Team2Score = (SELECT Team2Score FROM result_overrides o WHERE o.MatchId = matches.MatchId)
            WHERE MatchId IN (SELECT MatchId FROM result_overrides)
        """)
        self.conn.commit()

    def get_result_override_ids(self):
        self.cursor.execute("SELECT MatchId FROM result_overrides")
        return {row[0] for row in self.cursor.fetchall()}

    def save_market_odds(self, match_id, team1_percent, team2_percent, slug, closing):
        self.cursor.execute("""
            INSERT INTO market_odds (MatchId, Team1Percent, Team2Percent, Slug, Closing, FetchedAt) VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(MatchId) DO UPDATE SET Team1Percent = excluded.Team1Percent, Team2Percent = excluded.Team2Percent,
                Slug = excluded.Slug, Closing = excluded.Closing, FetchedAt = excluded.FetchedAt
        """, (match_id, team1_percent, team2_percent, slug, 1 if closing else 0))
        self.conn.commit()

    def get_market_odds(self, match_id):
        """(team1 percent, team2 percent, slug, closing) or None"""
        self.cursor.execute("SELECT Team1Percent, Team2Percent, Slug, Closing FROM market_odds WHERE MatchId=?", (match_id,))
        return self.cursor.fetchone()

    def set_reminder(self, user_id, enabled):
        if enabled:
            self.cursor.execute("INSERT OR IGNORE INTO reminder_users (UserID) VALUES (?)", (user_id,))
        else:
            self.cursor.execute("DELETE FROM reminder_users WHERE UserID=?", (user_id,))
        self.conn.commit()

    def get_reminder_users(self):
        self.cursor.execute("SELECT UserID FROM reminder_users")
        return [row[0] for row in self.cursor.fetchall()]

    def get_open_posted_matches(self):
        self.cursor.execute("""
            SELECT pm.MatchId, pm.ChannelId, pm.MessageId, m.DateTime_UTC, m.Team1, m.Team2
            FROM posted_messages pm JOIN matches m ON pm.MatchId = m.MatchId
            WHERE pm.State = 'open'
            ORDER BY m.DateTime_UTC
        """)
        return self.cursor.fetchall()

    def get_predicted_user_ids(self, match_id):
        self.cursor.execute("SELECT UserID FROM predictions WHERE MatchId=?", (match_id,))
        return {row[0] for row in self.cursor.fetchall()}

    def delete_posted_message(self, match_id):
        self.cursor.execute("DELETE FROM posted_messages WHERE MatchId=?", (match_id,))
        self.conn.commit()

    def count(self, table):
        # only used with fixed table names from the code, never user input
        self.cursor.execute(f"SELECT COUNT(*) FROM {table}")
        return self.cursor.fetchone()[0]

    def backup_to(self, path):
        destination = sqlite3.connect(path)
        with destination:
            self.conn.backup(destination)
        destination.close()

    def replace_teams(self, teams):
        """teams: list of (team, stage). Replaces the whole list, so teams removed on leaguepedia disappear too."""
        self.cursor.execute("DELETE FROM teams")
        self.cursor.executemany("INSERT OR IGNORE INTO teams (Team, Stage) VALUES (?, ?)", teams)
        self.conn.commit()

    def get_teams(self):
        self.cursor.execute("SELECT Team, Stage FROM teams ORDER BY Team COLLATE NOCASE")
        return self.cursor.fetchall()

    def get_full_matches(self):
        self.cursor.execute("SELECT * FROM matches ORDER BY DateTime_UTC")
        return self.cursor.fetchall()

    def set_bonus_picks(self, user_id, username, category, teams):
        self.cursor.execute("DELETE FROM bonus_picks WHERE UserID=? AND Category=?", (user_id, category))
        self.cursor.executemany(
            "INSERT INTO bonus_picks (UserID, Username, Category, Team) VALUES (?, ?, ?, ?)",
            [(user_id, username, category, team) for team in teams]
        )
        # keep the display name consistent across categories
        self.cursor.execute("UPDATE bonus_picks SET Username=? WHERE UserID=?", (username, user_id))
        self.conn.commit()

    def get_bonus_picks(self, user_id=None):
        if user_id is None:
            self.cursor.execute("SELECT UserID, Username, Category, Team FROM bonus_picks")
        else:
            self.cursor.execute("SELECT UserID, Username, Category, Team FROM bonus_picks WHERE UserID=?", (user_id,))
        return self.cursor.fetchall()

    def get_state(self, key):
        self.cursor.execute("SELECT Value FROM bot_state WHERE Key=?", (key,))
        row = self.cursor.fetchone()
        return row[0] if row else None

    def set_state(self, key, value):
        self.cursor.execute("INSERT INTO bot_state (Key, Value) VALUES (?, ?) ON CONFLICT(Key) DO UPDATE SET Value = excluded.Value", (key, value))
        self.conn.commit()

    def store_prediction(self, user_id, username, match_id, tournament, datetime_utc, best_of, team1, team2, predicted_winner, predicted_team1_score, predicted_team2_score):
        self.cursor.execute("""
            INSERT INTO predictions (UserID, Username, MatchId, Tournament, DateTime_UTC, BestOf, Team1, Team2, PredictedWinner, PredictedTeam1Score, PredictedTeam2Score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(UserID, MatchId) DO UPDATE SET
                Username = excluded.Username,
                Tournament = excluded.Tournament,
                DateTime_UTC = excluded.DateTime_UTC,
                BestOf = excluded.BestOf,
                Team1 = excluded.Team1,
                Team2 = excluded.Team2,
                PredictedWinner = excluded.PredictedWinner,
                PredictedTeam1Score = excluded.PredictedTeam1Score,
                PredictedTeam2Score = excluded.PredictedTeam2Score
        """, (user_id, username, match_id, tournament, datetime_utc, best_of, team1, team2, predicted_winner, predicted_team1_score, predicted_team2_score))
        self.conn.commit()

    def get_match_details(self, match_id):
        self.cursor.execute("SELECT * FROM matches WHERE MatchId=?", (match_id,))
        return self.cursor.fetchone()

    def get_upcoming_matches(self, start_time, end_time):
        # times are stored as 'YYYY-MM-DD HH:MM:SS' strings, so compare against strings of the same format
        self.cursor.execute(
            "SELECT * FROM matches WHERE DateTime_UTC >= ? AND DateTime_UTC <= ? ORDER BY DateTime_UTC",
            (start_time.strftime('%Y-%m-%d %H:%M:%S'), end_time.strftime('%Y-%m-%d %H:%M:%S'))
        )
        return self.cursor.fetchall()

    def upsert_match(self, match_id, tournament_name, date_time_utc, best_of, team1, team2, winner, team1_score, team2_score):
        # matches can be rescheduled and tiebreakers get filled in later, so every field is refreshed
        self.cursor.execute("""
            INSERT INTO matches (MatchId, Tournament, DateTime_UTC, BestOf, Team1, Team2, Winner, Team1Score, Team2Score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(MatchId) DO UPDATE SET
                Tournament = excluded.Tournament,
                DateTime_UTC = excluded.DateTime_UTC,
                BestOf = excluded.BestOf,
                Team1 = excluded.Team1,
                Team2 = excluded.Team2,
                Winner = excluded.Winner,
                Team1Score = excluded.Team1Score,
                Team2Score = excluded.Team2Score
        """, (match_id, tournament_name, date_time_utc, best_of, team1, team2, winner, team1_score, team2_score))
        self.conn.commit()

    def get_all_matches(self):
        self.cursor.execute("SELECT MatchId, BestOf, Winner, Team1Score, Team2Score FROM matches")
        return self.cursor.fetchall()

    def get_all_predictions(self):
        self.cursor.execute("SELECT UserID, Username, MatchId, PredictedWinner, PredictedTeam1Score, PredictedTeam2Score FROM predictions")
        return self.cursor.fetchall()

    def get_user_predictions(self, user_id):
        self.cursor.execute("""
            SELECT p.MatchId, p.BestOf, p.Team1, p.Team2, p.PredictedWinner, p.PredictedTeam1Score, p.PredictedTeam2Score,
                   m.DateTime_UTC, m.Winner, m.Team1Score, m.Team2Score
            FROM predictions p LEFT JOIN matches m ON p.MatchId = m.MatchId
            WHERE p.UserID = ?
            ORDER BY m.DateTime_UTC
        """, (user_id,))
        return self.cursor.fetchall()

    def get_match_predictions(self, match_id):
        self.cursor.execute("SELECT Username, PredictedWinner, PredictedTeam1Score, PredictedTeam2Score FROM predictions WHERE MatchId=?", (match_id,))
        return self.cursor.fetchall()

    def get_posted_message(self, match_id):
        self.cursor.execute("SELECT ChannelId, MessageId, State FROM posted_messages WHERE MatchId=?", (match_id,))
        return self.cursor.fetchone()

    def get_unfinished_posted_messages(self):
        self.cursor.execute("""
            SELECT pm.MatchId, pm.ChannelId, pm.MessageId, pm.State, m.Tournament, m.DateTime_UTC, m.BestOf, m.Team1, m.Team2, m.Winner, m.Team1Score, m.Team2Score
            FROM posted_messages pm JOIN matches m ON pm.MatchId = m.MatchId
            WHERE pm.State != 'final'
        """)
        return self.cursor.fetchall()

    def save_posted_message(self, match_id, channel_id, message_id, state):
        self.cursor.execute("""
            INSERT INTO posted_messages (MatchId, ChannelId, MessageId, State) VALUES (?, ?, ?, ?)
            ON CONFLICT(MatchId) DO UPDATE SET ChannelId = excluded.ChannelId, MessageId = excluded.MessageId, State = excluded.State
        """, (match_id, channel_id, message_id, state))
        self.conn.commit()

    def set_posted_message_state(self, match_id, state):
        self.cursor.execute("UPDATE posted_messages SET State=? WHERE MatchId=?", (state, match_id))
        self.conn.commit()

    def close(self):
        self.conn.close()
