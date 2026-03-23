import os
import requests
import time
from dotenv import load_dotenv
from database import db

load_dotenv()

API_KEY = os.getenv("SPORTRADAR_API_KEY")
API_LEVEL = os.getenv("NFL_API_LEVEL", "trial")
API_VERSION = os.getenv("NFL_API_VERSION", "v7")
# Updated base URL based on search results
BASE_URL = f"https://api.sportradar.com/nfl/official/{API_LEVEL}/{API_VERSION}/en"

class SportRadarAPI:
    def __init__(self, api_key):
        self.api_key = api_key

    def get_hierarchy(self):
        url = f"{BASE_URL}/league/hierarchy.json"
        params = {"api_key": self.api_key}
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching hierarchy: {response.status_code}")
            return None

    def get_team_profile(self, team_id):
        url = f"{BASE_URL}/teams/{team_id}/profile.json"
        params = {"api_key": self.api_key}
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            print("Rate limit exceeded. Waiting 2 seconds...")
            time.sleep(2)
            return self.get_team_profile(team_id)
        else:
            print(f"Error fetching team {team_id}: {response.status_code}")
            return None

    def populate_players_db(self):
        hierarchy = self.get_hierarchy()
        if not hierarchy:
            return

        players_added = 0
        teams_processed = 0
        
        for conference in hierarchy.get("conferences", []):
            for division in conference.get("divisions", []):
                for team in division.get("teams", []):
                    team_id = team.get("id")
                    team_name = team.get("name")
                    team_market = team.get("market")
                    
                    print(f"Processing team: {team_market} {team_name}...")
                    profile = self.get_team_profile(team_id)
                    
                    if profile and "players" in profile:
                        for player in profile["players"]:
                            player_doc = {
                                "id": player.get("id"),
                                "name": player.get("name"),
                                "position": player.get("position"),
                                "team": f"{team_market} {team_name}",
                                "status": player.get("status"),
                                "jersey": player.get("jersey")
                            }
                            db.add_player_to_db(player_doc)
                            players_added += 1
                        
                        teams_processed += 1
                        # Sleep to respect rate limits (trial keys are usually 1 call per second)
                        time.sleep(1.2)
        
        print(f"Added/Updated {players_added} players to the database from {teams_processed} teams.")

if __name__ == "__main__":
    sr_api = SportRadarAPI(API_KEY)
    sr_api.populate_players_db()
