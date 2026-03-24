import os
from pymongo import MongoClient
from dotenv import load_dotenv
import bcrypt

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/fantasy_football")

class Database:
    def __init__(self, mongodb_uri=None):
        uri = mongodb_uri or MONGODB_URI
        self.client = MongoClient(uri)
        self.db = self.client.get_database()
        self.users = self.db.users
        self.players = self.db.players
        self.rosters = self.db.rosters
        self.roster_freeze = self.db.roster_freeze
        self.leagues = self.db.leagues
        self.site_admins = self.db.site_admins
        self.trades = self.db.trades
        self.announcements = self.db.announcements
        self.nfl_games = self.db.nfl_games
        self.nfl_schedule = self.db.nfl_schedule
        self.nfl_teams = self.db.nfl_teams

    def create_announcement(self, announcement_type, message, user_id):
        import uuid
        from datetime import datetime, timezone
        announcement = {
            "id": str(uuid.uuid4()),
            "type": announcement_type,
            "message": message,
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc)
        }
        return self.announcements.insert_one(announcement)

    def create_trade(self, trade_id, league_id, offering_team, responding_team):
        from datetime import datetime, timezone
        trade = {
            "id": trade_id,
            "league_id": league_id,
            "team_offering": offering_team, # {team_id: str, player_ids: [], draft_picks: []}
            "team_responding": responding_team, # {team_id: str, player_ids: [], draft_picks: []}
            "status": "Pending",
            "status_modified": datetime.now(timezone.utc)
        }
        return self.trades.insert_one(trade)

    def get_trade(self, trade_id):
        return self.trades.find_one({"id": trade_id})

    def update_trade_status(self, trade_id, status):
        from datetime import datetime, timezone
        return self.trades.update_one({"id": trade_id}, {"$set": {
            "status": status,
            "status_modified": datetime.now(timezone.utc)
        }})

    def get_league_trades(self, league_id):
        return list(self.trades.find({"league_id": league_id}))

    def create_site_admin(self, admin_uuid, user_id, powers):
        admin = {
            "id": admin_uuid,
            "user_id": user_id,
            "powers": powers
        }
        return self.site_admins.insert_one(admin)

    def is_site_admin(self, user_id):
        return self.site_admins.find_one({"user_id": user_id}) is not None

    def create_league(self, league_id, name, league_type, scoring_format, positional_format, play_format, max_teams, has_divisions=False, num_divisions=None, user_ids=None, administrators=None):
        if user_ids is None:
            user_ids = []
        if administrators is None:
            administrators = []
        
        division_names = []
        if has_divisions and num_divisions:
            division_names = [f"Division {i+1}" for i in range(int(num_divisions))]

        default_scoring = {
            "passing": {
                "td": 6.0,
                "yard": 0.1,
                "attempt": 0.2,
                "completion": 0.5,
                "interception": -2.0
            },
            "rushing": {
                "td": 6.0,
                "yard": 0.1,
                "attempt": 0.2
            },
            "receiving": {
                "td": 6.0,
                "yard": 0.1,
                "reception": 1.0
            },
            "misc": {
                "fumble_lost": -3.0
            }
        }

        league = {
            "id": league_id,
            "name": name,
            "league_type": league_type,
            "scoring_format": scoring_format,
            "positional_format": positional_format,
            "play_format": play_format,
            "max_teams": int(max_teams),
            "has_divisions": bool(has_divisions),
            "num_divisions": int(num_divisions) if num_divisions else None,
            "division_names": division_names,
            "division_assignments": {str(i): [] for i in range(len(division_names))},
            "user_ids": user_ids,
            "administrators": administrators,
            "scoring_settings": default_scoring
        }
        return self.leagues.insert_one(league)

    def get_league(self, league_id):
        return self.leagues.find_one({"id": league_id})

    def get_league_scoring_settings(self, league_id):
        league = self.get_league(league_id)
        if league and 'scoring_settings' in league:
            return league['scoring_settings']
        # Fallback to defaults if not present
        return {
            "passing": {"td": 6.0, "yard": 0.1, "attempt": 0.2, "completion": 0.5, "interception": -2.0},
            "rushing": {"td": 6.0, "yard": 0.1, "attempt": 0.2},
            "receiving": {"td": 6.0, "yard": 0.1, "reception": 1.0},
            "misc": {"fumble_lost": -3.0}
        }

    def add_user_to_league(self, league_id, user_id):
        return self.leagues.update_one(
            {"id": league_id},
            {"$addToSet": {"user_ids": user_id}}
        )

    def remove_user_from_league(self, league_id, user_id):
        return self.leagues.update_one(
            {"id": league_id},
            {"$pull": {"user_ids": user_id, "administrators": user_id}}
        )

    def add_administrator_to_league(self, league_id, user_id):
        return self.leagues.update_one(
            {"id": league_id},
            {"$addToSet": {"administrators": user_id}}
        )

    def remove_administrator_from_league(self, league_id, user_id):
        return self.leagues.update_one(
            {"id": league_id},
            {"$pull": {"administrators": user_id}}
        )

    def update_league(self, league_id, update_data):
        return self.leagues.update_one(
            {"id": league_id},
            {"$set": update_data}
        )

    def delete_league(self, league_id):
        return self.leagues.delete_one({"id": league_id})

    def get_user(self, username):
        return self.users.find_one({"username": username})

    def get_user_by_id(self, user_id):
        from bson import ObjectId
        return self.users.find_one({"_id": ObjectId(user_id)})

    def create_user(self, username, password, email):
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        user = {
            "username": username,
            "password": hashed_password,
            "email": email,
            "is_site_admin": False,
            "announcements": []
        }
        return self.users.insert_one(user)

    def add_announcement_to_user(self, user_id, announcement_id):
        from bson import ObjectId
        return self.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$push": {"announcements": {
                "announcement_id": announcement_id,
                "heard": False,
                "heard_at": None
            }}}
        )

    def mark_announcement_as_heard(self, user_id, announcement_id):
        from bson import ObjectId
        from datetime import datetime, timezone
        return self.users.update_one(
            {"_id": ObjectId(user_id), "announcements.announcement_id": announcement_id},
            {"$set": {
                "announcements.$.heard": True,
                "announcements.$.heard_at": datetime.now(timezone.utc)
            }}
        )

    def set_site_admin(self, user_id, status=True):
        from bson import ObjectId
        return self.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"is_site_admin": status}}
        )

    def update_user(self, user_id, update_data):
        from bson import ObjectId
        # Remove sensitive or non-updatable fields if they somehow got in
        update_data.pop('_id', None)
        update_data.pop('password', None) # Separate method for password usually
        
        return self.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )

    def verify_password(self, password, hashed_password):
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password)

    def update_user_last_visited(self, user_id):
        from datetime import datetime, timezone
        from bson import ObjectId
        return self.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"last_visited": datetime.now(timezone.utc)}}
        )

    def get_all_players(self):
        return list(self.players.find({"position": {"$in": ["QB", "RB", "FB", "WR", "TE", "K"]}}))

    def get_player_by_id(self, player_id):
        return self.players.find_one({"id": player_id})

    def add_player_to_db(self, player_data):
        return self.players.update_one(
            {"id": player_data["id"]},
            {"$set": player_data},
            upsert=True
        )

    def get_roster(self, user_id, league_id=None):
        query = {"user_id": user_id}
        if league_id:
            query["league_id"] = league_id
        return self.rosters.find_one(query)

    def update_roster(self, user_id, league_id, player_ids, team_data=None):
        update_fields = {"player_ids": player_ids}
        if team_data:
            update_fields["team"] = team_data
        return self.rosters.update_one(
            {"user_id": user_id, "league_id": league_id},
            {"$set": update_fields},
            upsert=True
        )

    def add_draft_pick_to_roster(self, user_id, league_id, team_id, year, round_num, pick_num):
        pick = {
            "team_id": str(team_id),
            "year": int(year),
            "round": int(round_num),
            "pick": int(pick_num)
        }
        return self.rosters.update_one(
            {"user_id": user_id, "league_id": league_id},
            {"$push": {"team.draft_picks": pick}}
        )

    def remove_draft_pick_from_roster(self, user_id, league_id, team_id, year, round_num, pick_num):
        return self.rosters.update_one(
            {"user_id": user_id, "league_id": league_id},
            {"$pull": {"team.draft_picks": {"team_id": str(team_id), "year": int(year), "round": int(round_num), "pick": int(pick_num)}}}
        )

    def update_fantasy_team_info(self, user_id, league_id, team_name, acronym, fight_song):
        # We use $set for name, acronym, fight_song but want to preserve draft_picks if it exists
        # or initialize it if it doesn't.
        return self.rosters.update_one(
            {"user_id": user_id, "league_id": league_id},
            {
                "$set": {
                    "team.name": team_name,
                    "team.acronym": acronym,
                    "team.fight_song": fight_song
                },
                "$setOnInsert": {
                    "team.draft_picks": []
                }
            },
            upsert=True
        )

    def freeze_roster(self, user_id, player_ids, week_number):
        return self.roster_freeze.update_one(
            {"user_id": user_id, "week_number": week_number},
            {"$set": {"player_ids": player_ids}},
            upsert=True
        )

    def get_frozen_roster(self, user_id, week_number):
        return self.roster_freeze.find_one({"user_id": user_id, "week_number": week_number})

    def get_all_teams(self):
        return list(self.nfl_teams.find({"name": {"$ne": "TBD"}}))

db = Database()
