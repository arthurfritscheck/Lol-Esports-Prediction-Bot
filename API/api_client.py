import asyncio
from mwrogue.esports_client import EsportsClient
from mwrogue.auth_credentials import AuthCredentials
import config


def to_int(value):
    # leaguepedia returns everything as strings, with '' for missing values (unplayed matches, TBD formats, forfeits)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class APIHandler:
    def __init__(self, db):
        self.db = db
        self.site = None

    def connect(self):
        if config.LEAGUEPEDIA_USERNAME and config.LEAGUEPEDIA_PASSWORD:
            credentials = AuthCredentials(username=config.LEAGUEPEDIA_USERNAME, password=config.LEAGUEPEDIA_PASSWORD)
            self.site = EsportsClient("lol", credentials=credentials)
            print("Logged in to Leaguepedia.")
        else:
            # anonymous access is heavily rate limited, a bot password is strongly recommended
            self.site = EsportsClient("lol")
            print("No Leaguepedia credentials set, using anonymous access.")

    def fetch_matches(self):
        if self.site is None:
            self.connect()

        prefix = config.TOURNAMENT_PAGE_PREFIX.replace("'", "\\'")
        return self.site.cargo_client.query(
            tables="MatchSchedule=MS, Tournaments=T",
            join_on="MS.OverviewPage=T.OverviewPage",
            fields="MS.MatchId, T.Name, MS.DateTime_UTC, MS.BestOf, MS.Team1, MS.Team2, MS.Winner, MS.Team1Score, MS.Team2Score",
            where=f"MS.OverviewPage LIKE '{prefix}%'",
            order_by="MS.DateTime_UTC",
            limit=500
        )

    async def update_match_data(self):
        try:
            # mwrogue is synchronous, run it in a thread so the bot doesn't freeze during the request
            response = await asyncio.to_thread(self.fetch_matches)

            for record in response:
                if not record['MatchId'] or not record['DateTime UTC']:
                    continue
                self.db.upsert_match(
                    record['MatchId'],
                    record['Name'],
                    record['DateTime UTC'],
                    to_int(record['BestOf']),
                    record['Team1'],
                    record['Team2'],
                    to_int(record['Winner']),
                    to_int(record['Team1Score']),
                    to_int(record['Team2Score'])
                )
            print(f"Match data updated ({len(response)} matches).")
            return True

        except Exception as e:
            print(f"An error occurred whilst updating match data: {e}")
            # force a fresh login next time in case the session expired
            self.site = None
            return False
