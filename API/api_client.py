import sqlite3
from mwrogue.esports_client import EsportsClient
from datetime import datetime, timedelta, timezone
from database.database import MatchDatabase
import os
from dotenv import load_dotenv

load_dotenv()

class APIHandler:
    def __init__(self, db_path):
        self.db_path = db_path
        self.site = EsportsClient("lol")
        self.db = MatchDatabase(db_path)

    def update_match_data(self):
        try:
            # fill in tournament names of interest
            tournament_names = ["Worlds Qualifying Series 2024", 'Worlds 2024 Play-In', 'Worlds 2024 Main Event']
            tournament_names_query_list = ', '.join([f"'{name}'" for name in tournament_names])
            
            db = os.getenv('database_name')
            conn = sqlite3.connect(db)
            cursor = conn.cursor()

            # query for series outcomes
            response = self.site.cargo_client.query(
                tables="MatchSchedule=MS, Tournaments=T",
                join_on="MS.OverviewPage=T.OverviewPage",
                fields="MS.MatchId, T.Name, MS.DateTime_UTC, MS.BestOf, MS.Team1, MS.Team2, MS.Winner, MS.Team1Score, MS.Team2Score",
                where=f"T.Name IN ({tournament_names_query_list})",
                limit=500
            )

            for record in response:
                match_id = record['MatchId']
                tournament_name = record['Name']
                date_time_utc = record['DateTime UTC']
                best_of = record['BestOf']
                team1 = record['Team1']
                team2 = record['Team2']
                winner = record['Winner']
                team1_score = record['Team1Score']
                team2_score = record['Team2Score']

                print(f"Upserting match :{record}")
                print("\n")
                self.db.upsert_match(match_id, tournament_name, date_time_utc, best_of, team1, team2, winner, team1_score, team2_score)

        except Exception as e:
            print(f"An error occurred whilst updating match data: {e}")