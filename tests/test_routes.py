import pytest
from flask import url_for, session
from database import db
from bson import ObjectId
import uuid

def test_index_route(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b"Fantasy Football" in response.data

def test_register_route_get(client):
    response = client.get('/register')
    assert response.status_code == 200
    assert b"Register" in response.data

def test_register_route_post(client):
    username = "testuser_" + str(uuid.uuid4())[:8]
    response = client.post('/register', data={
        'username': username,
        'password': 'testpassword',
        'email': 'test@example.com'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Registration successful" in response.data
    assert db.get_user(username) is not None

def test_login_route_get(client):
    response = client.get('/login')
    assert response.status_code == 200
    assert b"Login" in response.data

def test_login_route_post(client):
    username = "loginuser_" + str(uuid.uuid4())[:8]
    db.create_user(username, "loginpass", "login@example.com")
    
    response = client.post('/login', data={
        'username': username,
        'password': 'loginpass'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"My Leagues" in response.data # Redirects to leagues_my

def test_admin_route_unauthorized(client):
    response = client.get('/admin', follow_redirects=True)
    assert b"Unauthorized access" in response.data

def test_admin_route_authorized(client, app):
    with client.session_transaction() as sess:
        sess['user_id'] = str(ObjectId())
        sess['is_site_admin'] = True
    
    response = client.get('/admin')
    assert response.status_code == 200
    assert b"Total Users" in response.data

def test_logout_route(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 'some_id'
    
    response = client.get('/logout', follow_redirects=True)
    assert response.status_code == 200
    assert b"Fantasy Football" in response.data # Back to index
    with client.session_transaction() as sess:
        assert 'user_id' not in sess

def test_profile_routes(client):
    user_id = str(db.create_user("profileuser", "pass", "profile@example.com").inserted_id)
    
    # Not logged in
    response = client.get('/profile/details', follow_redirects=True)
    assert b"Login" in response.data
    
    # Logged in
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = "profileuser"
    
    response = client.get('/profile/details')
    assert response.status_code == 200
    assert b"profileuser" in response.data

def test_nfl_routes(client):
    response = client.get('/nfl/home')
    assert response.status_code == 200
    
    response = client.get('/nfl/teams')
    assert response.status_code == 200
    
    response = client.get('/nfl/players')
    assert response.status_code == 200

def test_league_creation(client):
    user_id = str(db.create_user("leaguecreator", "pass", "league@example.com").inserted_id)
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = "leaguecreator"
    
    response = client.post('/leagues/create', data={
        'league_name': 'Test League',
        'league_type': 'Redraft',
        'scoring_format': 'PPR',
        'positional_format': 'Standard',
        'play_format': 'Head-to-Head',
        'max_teams': 12
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b"Test League" in response.data
    assert db.leagues.find_one({"name": "Test League"}) is not None

def test_join_league(client):
    user_id = str(db.create_user("joiner", "pass", "join@example.com").inserted_id)
    league_id = "test-league-id"
    db.create_league(league_id, "Joinable League", "Redraft", "PPR", "Standard", "H2H", 12)
    
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = "joiner"
        
    response = client.post(f'/join_league/{league_id}', follow_redirects=True)
    assert response.status_code == 200
    league = db.get_league(league_id)
    assert user_id in league['user_ids']

def test_league_home(client):
    user_id = str(db.create_user("member", "pass", "member@example.com").inserted_id)
    league_id = "home-league-id"
    db.create_league(league_id, "Home League", "Redraft", "PPR", "Standard", "H2H", 12, user_ids=[user_id])
    
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = "member"
        
    response = client.get(f'/league/{league_id}')
    assert response.status_code == 200
    assert b"Home League" in response.data

def test_nfl_team_route(client):
    db.nfl_teams.insert_one({
        "alias": "KC",
        "market": "Kansas City",
        "name": "Chiefs"
    })
    
    response = client.get('/nfl/team/KC')
    assert response.status_code == 200
    assert b"Kansas City" in response.data
    assert b"Chiefs" in response.data

def test_add_remove_player(client):
    user_id = str(db.create_user("rosteruser", "pass", "roster@example.com").inserted_id)
    player_id = "player123"
    db.players.insert_one({"id": player_id, "name": "Test Player", "position": "QB"})
    
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = "rosteruser"
        
    # Add
    client.get(f'/add_player/{player_id}', follow_redirects=True)
    roster = db.get_roster(user_id)
    assert player_id in roster['player_ids']
    
    # Remove
    client.get(f'/remove_player/{player_id}', follow_redirects=True)
    roster = db.get_roster(user_id)
    assert player_id not in roster['player_ids']

def test_trade_propose(client):
    user1_id = str(db.create_user("trader1", "pass", "t1@example.com").inserted_id)
    user2_id = str(db.create_user("trader2", "pass", "t2@example.com").inserted_id)
    league_id = "trade-league"
    db.create_league(league_id, "Trade League", "Dynasty", "PPR", "Standard", "H2H", 12, user_ids=[user1_id, user2_id])
    
    with client.session_transaction() as sess:
        sess['user_id'] = user1_id
        
    response = client.post(f'/league/{league_id}/trade/propose', data={
        'target_user_id': user2_id,
        'my_assets': ['player_p1'],
        'target_assets': ['player_p2']
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert db.trades.find_one({"league_id": league_id}) is not None

def test_announcement_broadcast(client):
    god_id = db.users.insert_one({
        "username": "god",
        "password": b"hashed",
        "email": "god@heaven.com",
        "is_god": True
    }).inserted_id
    
    user_id = db.create_user("mortal", "pass", "m@earth.com").inserted_id
    
    with client.session_transaction() as sess:
        sess['user_id'] = str(god_id)
        
    client.post('/speak', data={'message': 'Hear my word'}, follow_redirects=True)
    
    mortal = db.get_user_by_id(str(user_id))
    assert len(mortal.get('announcements', [])) == 1
