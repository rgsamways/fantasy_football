import os
import uuid
from pymongo import MongoClient
from dotenv import load_dotenv
import bcrypt
from datetime import datetime, timezone

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
        self.fantasy_matchups = self.db.fantasy_matchups
        self.leagues = self.db.leagues
        self.site_admins = self.db.site_admins
        self.trades = self.db.trades
        self.announcements = self.db.announcements
        self.nfl_games = self.db.nfl_games
        self.nfl_schedule = self.db.nfl_schedule
        self.nfl_teams = self.db.nfl_teams
        self.waiver_claims = self.db.waiver_claims

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

        default_roster_settings = [
            {"name": "QB", "count": 1, "positions": ["QB"]},
            {"name": "RB", "count": 2, "positions": ["RB", "FB"]},
            {"name": "WR", "count": 2, "positions": ["WR"]},
            {"name": "TE", "count": 1, "positions": ["TE"]},
            {"name": "FLEX", "count": 1, "positions": ["RB", "WR", "TE", "FB"]},
            {"name": "K", "count": 1, "positions": ["K"]}
        ]

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
            "scoring_settings": default_scoring,
            "current_season": 2026,
            "roster_settings": default_roster_settings,
            "salary_settings": {
                "active_model": "none", # points, touchdowns, performance_floor, auction, nfl_mirror, tiered, none
                "salary_cap": 100000000, # $100M default
                "point_multiplier": 100000, # $100k per point
                "td_value": 100000, # $100k per TD
                "base_salary": 500000, # $500k minimum
                "scaling_factor": 1.0
            },
            "important_dates": {
                "draft_date": None,
                "trading_deadline": None,
                "roster_lock": None,
                "playoffs_start": None,
                "season_end": None,
                "notes": ""
            },
            "rules": {
                "roster": {
                    "max_roster_size": 15,
                    "ir_slots": 1,
                    "waiver_type": "FAAB",
                    "faab_budget": 100,
                    "waiver_claim_window_hours": 24
                },
                "scoring": {
                    "bonus_100_rush_yards": 0.0,
                    "bonus_100_rec_yards": 0.0,
                    "bonus_300_pass_yards": 0.0,
                    "bonus_rush_td_40_plus": 0.0,
                    "bonus_rec_td_40_plus": 0.0,
                    "bonus_pass_td_40_plus": 0.0
                },
                "trading": {
                    "trading_enabled": True,
                    "review_period_hours": 48,
                    "trade_deadline_week": 11,
                    "max_players_per_trade": 5,
                    "veto_votes_required": 3
                },
                "draft": {
                    "draft_type": "Snake",
                    "order_method": "Random",
                    "pick_time_limit_seconds": 120,
                    "autopick_enabled": True
                },
                "playoffs": {
                    "regular_season_weeks": 14,
                    "playoff_teams": 4,
                    "seeding_method": "Record then Points",
                    "tiebreaker": "Total Points For"
                },
                "conduct": {
                    "collusion_policy": "Any team found colluding will be immediately removed from the league.",
                    "inactive_team_policy": "Teams with no lineup changes for 2 consecutive weeks may be replaced.",
                    "commissioner_veto": True
                }
            }
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
        roster = self.rosters.find_one(query)
        if roster and 'starters' not in roster:
            # Migration: Init empty starters if not exists
            self.rosters.update_one({"_id": roster['_id']}, {"$set": {"starters": {}}})
            roster['starters'] = {}
        return roster

    def update_roster(self, user_id, league_id, player_ids, team_data=None):
        update_fields = {"player_ids": player_ids}
        if team_data:
            update_fields["team"] = team_data
        
        # Ensure starters exists
        return self.rosters.update_one(
            {"user_id": user_id, "league_id": league_id},
            {
                "$set": update_fields,
                "$setOnInsert": {"starters": {}}
            },
            upsert=True
        )

    def set_starter(self, user_id, league_id, player_id, slot):
        """Sets a player to a specific starting slot (e.g., 'QB', 'RB1', 'FLEX')."""
        return self.rosters.update_one(
            {"user_id": user_id, "league_id": league_id},
            {"$set": {f"starters.{slot}": player_id}}
        )

    def bench_player(self, user_id, league_id, slot):
        """Removes a player from a starting slot."""
        return self.rosters.update_one(
            {"user_id": user_id, "league_id": league_id},
            {"$unset": {f"starters.{slot}": ""}}
        )

    def get_watchlist(self, user_id, league_id):
        """Returns the watchlist player_ids for a user in a league."""
        roster = self.rosters.find_one({"user_id": user_id, "league_id": league_id})
        return roster.get('watchlist', []) if roster else []

    def add_to_watchlist(self, user_id, league_id, player_id):
        """Adds a player to the watchlist if not already present."""
        return self.rosters.update_one(
            {"user_id": user_id, "league_id": league_id},
            {"$addToSet": {"watchlist": player_id}},
            upsert=True
        )

    def remove_from_watchlist(self, user_id, league_id, player_id):
        """Removes a player from the watchlist."""
        return self.rosters.update_one(
            {"user_id": user_id, "league_id": league_id},
            {"$pull": {"watchlist": player_id}}
        )

    # --- Waiver Claims ---

    def submit_waiver_claim(self, league_id, user_id, player_id, drop_player_id, week_number, priority):
        now = datetime.now(timezone.utc)
        claim = {
            "id": str(uuid.uuid4()),
            "league_id": league_id,
            "user_id": user_id,
            "player_id": player_id,
            "drop_player_id": drop_player_id,  # may be None
            "priority": priority,
            "status": "Pending",  # Pending | Awarded | Failed | Cancelled
            "week_number": week_number,
            "created_at": now,
            "processed_at": None,
            "fail_reason": None,
        }
        self.db.waiver_claims.insert_one(claim)
        return claim

    def get_waiver_claims(self, league_id, status=None, week_number=None):
        query = {"league_id": league_id}
        if status:
            query["status"] = status
        if week_number is not None:
            query["week_number"] = week_number
        return list(self.db.waiver_claims.find(query).sort("priority", 1))

    def get_user_waiver_claims(self, league_id, user_id, week_number=None):
        query = {"league_id": league_id, "user_id": user_id}
        if week_number is not None:
            query["week_number"] = week_number
        return list(self.db.waiver_claims.find(query).sort("created_at", -1))

    def cancel_waiver_claim(self, claim_id, user_id):
        return self.db.waiver_claims.update_one(
            {"id": claim_id, "user_id": user_id, "status": "Pending"},
            {"$set": {"status": "Cancelled"}}
        )

    def update_waiver_claim_status(self, claim_id, status, fail_reason=None):
        now = datetime.now(timezone.utc)
        update = {"status": status, "processed_at": now}
        if fail_reason:
            update["fail_reason"] = fail_reason
        return self.db.waiver_claims.update_one({"id": claim_id}, {"$set": update})

    def get_waiver_priority(self, league_id):
        """Returns ordered list of user_ids by waiver priority (index 0 = highest)."""
        league = self.get_league(league_id)
        return league.get("waiver_priority", league.get("user_ids", []))

    def set_waiver_priority(self, league_id, ordered_user_ids):
        return self.leagues.update_one(
            {"id": league_id},
            {"$set": {"waiver_priority": ordered_user_ids}}
        )

    def rotate_waiver_priority(self, league_id, user_id):
        """Move user_id to the end of the priority list after a successful claim."""
        priority = self.get_waiver_priority(league_id)
        if user_id in priority:
            priority.remove(user_id)
            priority.append(user_id)
        self.set_waiver_priority(league_id, priority)

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

    def create_invitation(self, league_id, email, inviter_id):
        """Creates a pending invitation record."""
        import secrets
        token = secrets.token_urlsafe(16)
        invitation = {
            "id": str(uuid.uuid4()),
            "token": token,
            "league_id": league_id,
            "email": email,
            "inviter_id": inviter_id,
            "status": "pending",
            "created_at": datetime.utcnow()
        }
        self.db.invitations.insert_one(invitation)
        return token

    def get_invitation_by_token(self, token):
        return self.db.invitations.find_one({"token": token, "status": "pending"})

    def get_league_invitations(self, league_id, status="pending"):
        return list(self.db.invitations.find({"league_id": league_id, "status": status}))

    def update_invitation_status(self, invitation_id, status):
        return self.db.invitations.update_one({"id": invitation_id}, {"$set": {"status": status}})

    def get_all_teams(self):
        return list(self.nfl_teams.find({"name": {"$ne": "TBD"}}))

    def generate_league_schedule(self, league_id, season_year):
        """Generates a 14-week Round Robin schedule for the league members."""
        league = self.get_league(league_id)
        if not league: return False
        
        user_ids = league.get('user_ids', [])
        if len(user_ids) < 2: return False
        
        # 1. Circle Method Round Robin Setup
        import random
        teams = list(user_ids)
        random.shuffle(teams)
        if len(teams) % 2 != 0:
            teams.append(None) # Bye team if odd number
        
        n = len(teams)
        weeks = 14 # Standard fantasy regular season
        matchups = []
        
        for wk in range(1, weeks + 1):
            for i in range(n // 2):
                h = teams[i]
                a = teams[n - 1 - i]
                
                if h and a:
                    matchups.append({
                        "id": str(uuid.uuid4()),
                        "league_id": league_id,
                        "season_year": int(season_year),
                        "week_number": wk,
                        "home_id": h,
                        "away_id": a,
                        "status": "scheduled"
                    })
            
            # Rotate circle: keep index 0, shift others
            teams = [teams[0]] + [teams[-1]] + teams[1:-1]

        # 2. Clear old schedule for this season and insert new
        self.fantasy_matchups.delete_many({"league_id": league_id, "season_year": int(season_year)})
        if matchups:
            self.fantasy_matchups.insert_many(matchups)
        return True

    def get_league_matchups(self, league_id, week_number, season_year):
        return list(self.fantasy_matchups.find({
            "league_id": league_id, 
            "week_number": int(week_number), 
            "season_year": int(season_year)
        }))

    def get_all_league_matchups(self, league_id, season_year):
        return list(self.fantasy_matchups.find({
            "league_id": league_id,
            "season_year": int(season_year)
        }))

    def initialize_draft(self, league_id, season_year):
        """Sets up the draft order and initial state for a league."""
        league = self.get_league(league_id)
        if not league: return False
        
        user_ids = list(league.get('user_ids', []))
        import random
        random.shuffle(user_ids) # Randomize initial order
        
        draft_state = {
            "league_id": league_id,
            "season_year": int(season_year),
            "order": user_ids, # Round 1 order
            "current_pick": 1,
            "status": "In-Progress",
            "picks": [] # List of {pick_number, round, user_id, player_id}
        }
        
        self.db.drafts.update_one(
            {"league_id": league_id, "season_year": int(season_year)},
            {"$set": draft_state},
            upsert=True
        )
        return True

    def get_draft_state(self, league_id, season_year):
        return self.db.drafts.find_one({"league_id": league_id, "season_year": int(season_year)})

    def make_draft_pick(self, league_id, season_year, user_id, player_id, pick_number, round_number):
        """Records a pick and updates the manager's roster."""
        # 1. Record the pick in the draft state
        self.db.drafts.update_one(
            {"league_id": league_id, "season_year": int(season_year)},
            {
                "$push": {"picks": {
                    "pick_number": pick_number,
                    "round": round_number,
                    "user_id": user_id,
                    "player_id": player_id,
                    "timestamp": datetime.now(timezone.utc)
                }},
                "$inc": {"current_pick": 1}
            }
        )
        
        # 2. Add player to the manager's roster
        roster = self.get_roster(user_id, league_id)
        player_ids = roster.get('player_ids', []) if roster else []
        if player_id not in player_ids:
            player_ids.append(player_id)
            self.update_roster(user_id, league_id, player_ids)
            
        return True

    def get_site_settings(self):
        """Fetches global site settings from the database."""
        settings = self.db.site_settings.find_one({"id": "global"})
        if not settings:
            # Init with defaults
            default = {"id": "global", "current_season": 2025}
            self.db.site_settings.insert_one(default)
            return default
        return settings

    def update_site_settings(self, data):
        """Updates global site settings."""
        return self.db.site_settings.update_one(
            {"id": "global"},
            {"$set": data},
            upsert=True
        )

    # --- Achievements ---
    def get_achievement_definitions(self):
        """Returns all global achievement definitions."""
        return list(self.db.achievement_definitions.find())

    def get_user_achievements(self, user_id):
        """Returns all achievements earned or in progress for a specific user."""
        from bson import ObjectId
        user = self.db.users.find_one({"_id": ObjectId(user_id)}, {"achievements": 1})
        return user.get('achievements', []) if user else []

    def award_achievement(self, user_id, achievement_id, progress=100):
        """Awards an achievement or updates progress for a user."""
        from bson import ObjectId
        from datetime import datetime
        
        # Check if they already have it
        user = self.db.users.find_one({
            "_id": ObjectId(user_id),
            "achievements.achievement_id": achievement_id
        })
        
        if user:
            # Update existing progress
            return self.db.users.update_one(
                {"_id": ObjectId(user_id), "achievements.achievement_id": achievement_id},
                {"$set": {
                    "achievements.$.progress": progress,
                    "achievements.$.updated_at": datetime.utcnow()
                }}
            )
        else:
            # Add new achievement entry
            return self.db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$push": {"achievements": {
                    "achievement_id": achievement_id,
                    "progress": progress,
                    "earned_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }}}
            )

    # --- Message Board ---
    def get_threads(self, league_id):
        return list(self.db.message_board.find({"league_id": league_id}).sort([
            ("pinned", -1), ("last_post_at", -1)
        ]))

    def get_thread(self, thread_id):
        return self.db.message_board.find_one({"id": thread_id})

    def create_thread(self, league_id, author_id, title, content):
        now = datetime.now(timezone.utc)
        thread = {
            "id": str(uuid.uuid4()),
            "league_id": league_id,
            "title": title,
            "author_id": author_id,
            "created_at": now,
            "last_post_at": now,
            "post_count": 1,
            "pinned": False,
            "posts": [{
                "id": str(uuid.uuid4()),
                "author_id": author_id,
                "content": content,
                "created_at": now
            }]
        }
        self.db.message_board.insert_one(thread)
        return thread

    def add_post(self, thread_id, author_id, content):
        now = datetime.now(timezone.utc)
        post = {
            "id": str(uuid.uuid4()),
            "author_id": author_id,
            "content": content,
            "created_at": now
        }
        self.db.message_board.update_one(
            {"id": thread_id},
            {"$push": {"posts": post}, "$set": {"last_post_at": now}, "$inc": {"post_count": 1}}
        )
        return post

    def delete_post(self, thread_id, post_id):
        thread = self.get_thread(thread_id)
        if not thread: return
        remaining = [p for p in thread['posts'] if p['id'] != post_id]
        if not remaining:
            self.db.message_board.delete_one({"id": thread_id})
        else:
            last_post_at = remaining[-1]['created_at']
            self.db.message_board.update_one(
                {"id": thread_id},
                {"$set": {"posts": remaining, "post_count": len(remaining), "last_post_at": last_post_at}}
            )

    def delete_thread(self, thread_id):
        self.db.message_board.delete_one({"id": thread_id})

    def toggle_pin_thread(self, thread_id, pinned):
        self.db.message_board.update_one({"id": thread_id}, {"$set": {"pinned": pinned}})

    def mark_board_visited(self, user_id, league_id):
        from bson import ObjectId
        now = datetime.now(timezone.utc)
        self.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {f"board_visited.{league_id}": now}}
        )

    def get_board_last_visited(self, user_id, league_id):
        from bson import ObjectId
        user = self.db.users.find_one({"_id": ObjectId(user_id)}, {"board_visited": 1})
        if user:
            return user.get('board_visited', {}).get(league_id)
        return None

    def count_user_finalized_trades(self, user_id):
        """Count total finalized trades involving a user across all leagues."""
        return self.trades.count_documents({
            "status": "Finalized",
            "$or": [
                {"team_offering.team_id": user_id},
                {"team_responding.team_id": user_id}
            ]
        })

    def count_user_finalized_trades_in_league(self, user_id, league_id):
        """Count finalized trades for a user in a specific league."""
        return self.trades.count_documents({
            "league_id": league_id,
            "status": "Finalized",
            "$or": [
                {"team_offering.team_id": user_id},
                {"team_responding.team_id": user_id}
            ]
        })

    def get_user_trade_partners(self, user_id, league_id):
        """Return set of user_ids this user has completed trades with in a league."""
        trades = self.trades.find({
            "league_id": league_id,
            "status": "Finalized",
            "$or": [
                {"team_offering.team_id": user_id},
                {"team_responding.team_id": user_id}
            ]
        })
        partners = set()
        for t in trades:
            if t['team_offering']['team_id'] == user_id:
                partners.add(t['team_responding']['team_id'])
            else:
                partners.add(t['team_offering']['team_id'])
        return partners

    def count_user_posts(self, user_id):
        """Count total posts made by a user across all boards."""
        total = 0
        threads = self.db.message_board.find({"posts.author_id": user_id}, {"posts": 1})
        for t in threads:
            total += sum(1 for p in t.get('posts', []) if p['author_id'] == user_id)
        return total

    def count_user_threads(self, user_id):
        """Count total threads created by a user across all boards."""
        return self.db.message_board.count_documents({"author_id": user_id})

    # --- Weekly Snapshots ---
    def save_weekly_snapshot(self, snapshot):
        """Saves a point-in-time snapshot of weekly results."""
        # Using a unique ID based on season and week to allow updates/re-finalization
        snapshot_id = f"{snapshot['season']}_W{snapshot['week']}"
        return self.db.weekly_results.update_one(
            {"week_id": snapshot_id},
            {"$set": snapshot},
            upsert=True
        )

    def get_weekly_snapshot(self, season, week):
        """Retrieves a specific weekly snapshot."""
        snapshot_id = f"{season}_W{week}"
        return self.db.weekly_results.find_one({"week_id": snapshot_id})

db = Database()
