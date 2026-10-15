from datetime import datetime, timezone
import re
import discord
from match_message import render_match_message


class PredictButton(discord.ui.DynamicItem[discord.ui.Button], template=r'predict\$(?P<match_id>.+)\$(?P<team1_score>\d+)-(?P<team2_score>\d+)'):
    """
    Prediction button that keeps working after a bot restart.
    discord.py matches any clicked button whose custom_id fits the template and rebuilds it with from_custom_id.
    """

    def __init__(self, match_id, team1_score, team2_score, row=0, disabled=False):
        # blurple for team1 winning, red for team2 winning
        style = discord.ButtonStyle.blurple if team1_score > team2_score else discord.ButtonStyle.red
        super().__init__(
            discord.ui.Button(
                label=f"{team1_score}-{team2_score}",
                style=style,
                row=row,
                disabled=disabled,
                custom_id=f"predict${match_id}${team1_score}-{team2_score}"
            )
        )
        self.match_id = match_id
        self.team1_score = team1_score
        self.team2_score = team2_score

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match):
        return cls(match['match_id'], int(match['team1_score']), int(match['team2_score']))

    async def callback(self, interaction: discord.Interaction):
        try:
            db = interaction.client.db
            username = interaction.user.display_name

            match_details = db.get_match_details(self.match_id)
            if not match_details:
                await interaction.response.send_message("Match details not found!", ephemeral=True)
                return

            tournament, match_time_str, best_of, team1, team2 = match_details[1:6]
            match_time = datetime.strptime(match_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)

            if datetime.now(timezone.utc) >= match_time:
                await interaction.response.send_message("This match has already started, you cannot predict anymore.", ephemeral=True)
                return

            # 1 = team1 wins, 2 = team2 wins, for ease of comparison with leaguepedia's data
            predicted_winner = 1 if self.team1_score > self.team2_score else 2

            db.store_prediction(interaction.user.id, username, self.match_id, tournament, match_time_str, best_of, team1, team2,
                                predicted_winner, self.team1_score, self.team2_score)
            # only the user sees the confirmation, everyone sees the picks on the match message itself
            await interaction.response.send_message(
                f"You predicted **{team1} {self.team1_score}-{self.team2_score} {team2}**. You can change it until the match starts.",
                ephemeral=True
            )
            print(f"{username} predicted {self.team1_score}-{self.team2_score} for {team1}-{team2}.")

            try:
                # use the stored state, in case the background loop locked the message in the meantime
                posted = db.get_posted_message(self.match_id)
                state = posted[2] if posted else 'open'
                await interaction.message.edit(content=render_match_message(db, self.match_id, state))
            except discord.HTTPException as e:
                # the prediction is saved either way, the picks list catches up on the next edit
                print(f"Could not update picks on the match message: {e}")

        except Exception as e:
            print(f"An error occurred: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("An error occurred while processing your prediction. Please try again later.", ephemeral=True)


SCORE_OPTIONS = {
    1: [(1, 0), (0, 1)],
    3: [(2, 0), (2, 1), (1, 2), (0, 2)],
    5: [(3, 0), (3, 1), (3, 2), (2, 3), (1, 3), (0, 3)],
}


def build_prediction_view(match_id, best_of, disabled=False):
    view = discord.ui.View(timeout=None)
    for team1_score, team2_score in SCORE_OPTIONS.get(best_of, []):
        row = 0 if team1_score > team2_score else 1
        view.add_item(PredictButton(match_id, team1_score, team2_score, row=row, disabled=disabled))
    return view
