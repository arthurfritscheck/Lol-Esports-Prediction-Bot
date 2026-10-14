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
        self.cursor.execute("SELECT UserID, PredictedWinner, PredictedTeam1Score, PredictedTeam2Score FROM predictions WHERE MatchId=?", (match_id,))
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
