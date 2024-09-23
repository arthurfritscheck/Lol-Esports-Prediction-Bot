import sqlite3

class MatchDatabase:
    def __init__(self, db_path):
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
        self.cursor.execute("SELECT * FROM matches WHERE DateTime_UTC >= ? AND DateTime_UTC <= ?", (start_time, end_time))
        return self.cursor.fetchall()

    def upsert_match(self, match_id, tournament_name, date_time_utc, best_of, team1, team2, winner, team1_score, team2_score):
        self.cursor.execute("SELECT * FROM matches WHERE MatchId=?", (match_id,))
        existing_match = self.cursor.fetchone()

        if existing_match:
            self.cursor.execute(
                "UPDATE matches SET Team1=?, Team2=?, Winner=?, Team1Score=?, Team2Score=? WHERE MatchId=?", 
                (team1, team2, winner, team1_score, team2_score, match_id)
            )
        else:
            # first time insert
            # necessary in case of possible tiebreakers that have not been scheduled yet
            self.cursor.execute(
                "INSERT INTO matches (MatchId, Tournament, DateTime_UTC, BestOf, Team1, Team2, Winner, Team1Score, Team2Score) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (match_id, tournament_name, date_time_utc, best_of, team1, team2, winner, team1_score, team2_score)
            )
        self.conn.commit()
    
    def close(self):
        self.conn.close()