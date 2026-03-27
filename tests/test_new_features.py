import pytest
from flask import session
from database import db
from bson import ObjectId
import uuid


# ─── Helpers ────────────────────────────────────────────────────────────────

def make_user(suffix=None):
    suffix = suffix or str(uuid.uuid4())[:8]
    username = f"user_{suffix}"
    user_id = str(db.create_user(username, "password", f"{username}@test.com").inserted_id)
    return user_id, username


def login(client, user_id, username, is_admin=False):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = username
        sess['is_site_admin'] = is_admin
        sess['is_god'] = False


def make_league(user_id, name=None):
    league_id = str(uuid.uuid4())
    name = name or f"League {league_id[:6]}"
    db.create_league(league_id, name, "Redraft", "PPR", "Standard", "Head-2-Head", 12,
                     user_ids=[user_id], administrators=[user_id])
    return league_id


# ─── Auth ────────────────────────────────────────────────────────────────────

class TestAuth:
    def test_register_duplicate_username(self, client):
        db.create_user("dupuser", "pass", "dup@test.com")
        response = client.post('/register', data={
            'username': 'dupuser', 'password': 'pass', 'email': 'dup2@test.com'
        }, follow_redirects=True)
        assert b"Username already exists" in response.data

    def test_login_wrong_password(self, client):
        db.create_user("wrongpass", "correctpass", "wp@test.com")
        response = client.post('/login', data={
            'username': 'wrongpass', 'password': 'wrongpass'
        }, follow_redirects=True)
        assert b"Invalid username or password" in response.data

    def test_logout_clears_session(self, client):
        user_id, username = make_user()
        login(client, user_id, username)
        client.get('/logout')
        with client.session_transaction() as sess:
            assert 'user_id' not in sess


# ─── League ──────────────────────────────────────────────────────────────────

class TestLeague:
    def test_create_league_requires_login(self, client):
        response = client.post('/leagues/create', data={
            'league_name': 'No Auth', 'league_type': 'Redraft',
            'scoring_format': 'PPR', 'positional_format': 'Standard',
            'play_format': 'Head-2-Head', 'max_teams': 12
        }, follow_redirects=True)
        assert b"Login" in response.data

    def test_league_home_shows_members(self, client):
        user_id, username = make_user()
        league_id = make_league(user_id, "Members League")
        login(client, user_id, username)
        response = client.get(f'/league/{league_id}')
        assert response.status_code == 200
        assert username.encode() in response.data

    def test_league_not_found(self, client):
        user_id, username = make_user()
        login(client, user_id, username)
        response = client.get('/league/nonexistent-id', follow_redirects=True)
        assert b"League not found" in response.data

    def test_join_league_awards_draft_picks(self, client):
        user_id, username = make_user()
        league_id = make_league(user_id)
        joiner_id, joiner_name = make_user()
        login(client, joiner_id, joiner_name)
        client.post(f'/join_league/{league_id}', follow_redirects=True)
        roster = db.get_roster(joiner_id, league_id)
        assert roster is not None
        picks = roster.get('team', {}).get('draft_picks', [])
        assert len(picks) > 0

    def test_delete_league_only_creator(self, client):
        creator_id, creator_name = make_user()
        other_id, other_name = make_user()
        league_id = make_league(creator_id)
        db.add_user_to_league(league_id, other_id)
        login(client, other_id, other_name)
        response = client.post(f'/delete_league/{league_id}', follow_redirects=True)
        assert b"not authorized" in response.data
        assert db.get_league(league_id) is not None

    def test_important_dates_saved(self, client):
        user_id, username = make_user()
        league_id = make_league(user_id)
        login(client, user_id, username)
        client.post(f'/league/{league_id}/important_dates', data={
            'draft_date': 'Aug 1, 2026 7:00 PM',
            'trading_deadline': 'Nov 1, 2026',
            'roster_lock': '', 'playoffs_start': '', 'season_end': '', 'notes': 'Test note'
        })
        league = db.get_league(league_id)
        assert league['important_dates']['draft_date'] == 'Aug 1, 2026 7:00 PM'
        assert league['important_dates']['notes'] == 'Test note'


# ─── Roster ──────────────────────────────────────────────────────────────────

class TestRoster:
    def test_add_player_enforces_max_roster_size(self, client):
        user_id, username = make_user()
        league_id = make_league(user_id)
        db.update_league(league_id, {"rules": {"roster": {"max_roster_size": 2}}})
        login(client, user_id, username)
        for i in range(3):
            pid = f"player_{i}_{uuid.uuid4().hex[:6]}"
            db.players.insert_one({"id": pid, "name": f"Player {i}", "position": "QB", "team": "KC"})
            client.get(f'/add_player/{pid}/{league_id}', follow_redirects=True)
        roster = db.get_roster(user_id, league_id)
        assert len(roster.get('player_ids', [])) <= 2

    def test_remove_player_from_roster(self, client):
        user_id, username = make_user()
        league_id = make_league(user_id)
        pid = f"p_{uuid.uuid4().hex[:6]}"
        db.players.insert_one({"id": pid, "name": "Drop Me", "position": "WR", "team": "DAL"})
        db.update_roster(user_id, league_id, [pid])
        login(client, user_id, username)
        client.get(f'/remove_player/{pid}/{league_id}', follow_redirects=True)
        roster = db.get_roster(user_id, league_id)
        assert pid not in roster.get('player_ids', [])


# ─── Trading ─────────────────────────────────────────────────────────────────

class TestTrading:
    def _setup_trade(self, client):
        u1_id, u1_name = make_user()
        u2_id, u2_name = make_user()
        league_id = make_league(u1_id)
        db.add_user_to_league(league_id, u2_id)
        p1 = f"tp1_{uuid.uuid4().hex[:6]}"
        p2 = f"tp2_{uuid.uuid4().hex[:6]}"
        db.players.insert_one({"id": p1, "name": "Player A", "position": "QB", "team": "KC"})
        db.players.insert_one({"id": p2, "name": "Player B", "position": "RB", "team": "SF"})
        db.update_roster(u1_id, league_id, [p1])
        db.update_roster(u2_id, league_id, [p2])
        return u1_id, u1_name, u2_id, u2_name, league_id, p1, p2

    def test_propose_trade(self, client):
        u1_id, u1_name, u2_id, _, league_id, p1, p2 = self._setup_trade(client)
        login(client, u1_id, u1_name)
        response = client.post(f'/league/{league_id}/trade/propose', data={
            'target_user_id': u2_id,
            'my_assets': [f'player_{p1}'],
            'target_assets': [f'player_{p2}']
        }, follow_redirects=True)
        assert response.status_code == 200
        trade = db.trades.find_one({"league_id": league_id})
        assert trade is not None
        assert trade['status'] == 'Pending'

    def test_reject_trade(self, client):
        u1_id, u1_name, u2_id, u2_name, league_id, p1, p2 = self._setup_trade(client)
        trade_id = str(uuid.uuid4())
        db.create_trade(trade_id, league_id,
                        {"team_id": u1_id, "player_ids": [p1], "draft_picks": []},
                        {"team_id": u2_id, "player_ids": [p2], "draft_picks": []})
        login(client, u2_id, u2_name)
        client.post(f'/league/{league_id}/trade/{trade_id}/reject', follow_redirects=True)
        trade = db.get_trade(trade_id)
        assert trade['status'] == 'Rejected'

    def test_cancel_trade(self, client):
        u1_id, u1_name, u2_id, _, league_id, p1, p2 = self._setup_trade(client)
        trade_id = str(uuid.uuid4())
        db.create_trade(trade_id, league_id,
                        {"team_id": u1_id, "player_ids": [p1], "draft_picks": []},
                        {"team_id": u2_id, "player_ids": [p2], "draft_picks": []})
        login(client, u1_id, u1_name)
        client.post(f'/league/{league_id}/trade/{trade_id}/cancel', follow_redirects=True)
        trade = db.get_trade(trade_id)
        assert trade['status'] == 'Cancelled'


# ─── Message Board ───────────────────────────────────────────────────────────

class TestMessageBoard:
    def test_create_thread(self, client):
        user_id, username = make_user()
        league_id = make_league(user_id)
        login(client, user_id, username)
        response = client.post(f'/league/{league_id}/board/new', data={
            'title': 'Hello Board', 'content': 'First post!'
        }, follow_redirects=True)
        assert response.status_code == 200
        thread = db.db.message_board.find_one({"league_id": league_id})
        assert thread is not None
        assert thread['title'] == 'Hello Board'

    def test_reply_to_thread(self, client):
        user_id, username = make_user()
        league_id = make_league(user_id)
        thread = db.create_thread(league_id, user_id, "Test Thread", "Opening post")
        login(client, user_id, username)
        client.post(f'/league/{league_id}/board/{thread["id"]}', data={
            'content': 'A reply'
        }, follow_redirects=True)
        updated = db.get_thread(thread['id'])
        assert updated['post_count'] == 2

    def test_delete_thread_by_author(self, client):
        user_id, username = make_user()
        league_id = make_league(user_id)
        thread = db.create_thread(league_id, user_id, "Delete Me", "Content")
        login(client, user_id, username)
        client.post(f'/league/{league_id}/board/{thread["id"]}/delete', follow_redirects=True)
        assert db.get_thread(thread['id']) is None

    def test_delete_thread_unauthorized(self, client):
        owner_id, _ = make_user()
        other_id, other_name = make_user()
        league_id = make_league(owner_id)
        db.add_user_to_league(league_id, other_id)
        thread = db.create_thread(league_id, owner_id, "Protected", "Content")
        login(client, other_id, other_name)
        client.post(f'/league/{league_id}/board/{thread["id"]}/delete', follow_redirects=True)
        assert db.get_thread(thread['id']) is not None

    def test_pin_thread_admin_only(self, client):
        user_id, username = make_user()
        other_id, other_name = make_user()
        league_id = make_league(user_id)
        db.add_user_to_league(league_id, other_id)
        thread = db.create_thread(league_id, user_id, "Pin Me", "Content")
        # Non-admin cannot pin
        login(client, other_id, other_name)
        client.post(f'/league/{league_id}/board/{thread["id"]}/pin', follow_redirects=True)
        assert db.get_thread(thread['id'])['pinned'] is False
        # Admin can pin
        login(client, user_id, username)
        client.post(f'/league/{league_id}/board/{thread["id"]}/pin', follow_redirects=True)
        assert db.get_thread(thread['id'])['pinned'] is True


# ─── Achievements ────────────────────────────────────────────────────────────

class TestAchievements:
    def test_award_achievement(self):
        user_id, _ = make_user()
        db.award_achievement(user_id, 'first_trade')
        achievements = db.get_user_achievements(user_id)
        assert any(a['achievement_id'] == 'first_trade' for a in achievements)

    def test_award_achievement_no_duplicate(self):
        user_id, _ = make_user()
        db.award_achievement(user_id, 'first_trade', progress=100)
        db.award_achievement(user_id, 'first_trade', progress=100)
        achievements = db.get_user_achievements(user_id)
        assert sum(1 for a in achievements if a['achievement_id'] == 'first_trade') == 1

    def test_api_award_achievement_requires_login(self, client):
        response = client.post('/api/award_achievement',
                               json={'achievement_id': 'pull_the_shades_down'})
        assert response.status_code == 401

    def test_api_award_achievement_whitelist(self, client):
        user_id, username = make_user()
        login(client, user_id, username)
        # Allowed
        response = client.post('/api/award_achievement',
                               json={'achievement_id': 'pull_the_shades_down'})
        assert response.json['success'] is True
        # Not allowed
        response = client.post('/api/award_achievement',
                               json={'achievement_id': 'champion'})
        assert response.status_code == 403

    def test_first_pick_achievement_on_add_player(self, client):
        user_id, username = make_user()
        league_id = make_league(user_id)
        pid = f"fp_{uuid.uuid4().hex[:6]}"
        db.players.insert_one({"id": pid, "name": "First Pick", "position": "QB", "team": "KC"})
        login(client, user_id, username)
        client.get(f'/add_player/{pid}/{league_id}', follow_redirects=True)
        achievements = db.get_user_achievements(user_id)
        assert any(a['achievement_id'] == 'first_pick' for a in achievements)


# ─── League Rules ────────────────────────────────────────────────────────────

class TestLeagueRules:
    def test_rules_saved(self, client):
        user_id, username = make_user()
        league_id = make_league(user_id)
        login(client, user_id, username)
        client.post(f'/league/{league_id}/rules/save', data={
            'max_roster_size': 20, 'ir_slots': 2, 'waiver_type': 'Rolling',
            'faab_budget': 200, 'waiver_claim_window_hours': 48,
            'bonus_100_rush_yards': 2.0, 'bonus_100_rec_yards': 2.0,
            'bonus_300_pass_yards': 3.0, 'bonus_rush_td_40_plus': 0,
            'bonus_rec_td_40_plus': 0, 'bonus_pass_td_40_plus': 0,
            'trading_enabled': 'on', 'review_period_hours': 24,
            'trade_deadline_week': 10, 'max_players_per_trade': 4,
            'veto_votes_required': 2, 'draft_type': 'Auction',
            'order_method': 'Random', 'pick_time_limit_seconds': 60,
            'autopick_enabled': 'on', 'regular_season_weeks': 13,
            'playoff_teams': 6, 'seeding_method': 'Record then Points',
            'tiebreaker': 'Total Points For', 'collusion_policy': 'No cheating',
            'inactive_team_policy': 'Drop after 3 weeks'
        })
        league = db.get_league(league_id)
        assert league['rules']['roster']['max_roster_size'] == 20
        assert league['rules']['draft']['draft_type'] == 'Auction'
        assert league['rules']['playoffs']['playoff_teams'] == 6

    def test_rules_save_requires_admin(self, client):
        owner_id, _ = make_user()
        other_id, other_name = make_user()
        league_id = make_league(owner_id)
        db.add_user_to_league(league_id, other_id)
        login(client, other_id, other_name)
        response = client.post(f'/league/{league_id}/rules/save',
                               data={'max_roster_size': 99}, follow_redirects=True)
        assert b"Unauthorized" in response.data


# ─── API ─────────────────────────────────────────────────────────────────────

class TestAPI:
    def test_team_colors_endpoint(self, client):
        db.nfl_teams.insert_one({
            "alias": "TST", "market": "Test", "name": "Team",
            "team_colors": [
                {"type": "primary", "hex_color": "#ff0000"},
                {"type": "secondary", "hex_color": "#0000ff"}
            ]
        })
        response = client.get('/api/team_colors')
        assert response.status_code == 200
        data = response.json
        assert 'TST' in data
        assert data['TST']['primary'] == '#ff0000'
        assert data['TST']['secondary'] == '#0000ff'

    def test_team_colors_excludes_missing(self, client):
        db.nfl_teams.insert_one({
            "alias": "NOTST", "market": "No", "name": "Colors",
            "team_colors": []
        })
        response = client.get('/api/team_colors')
        data = response.json
        assert 'NOTST' not in data
