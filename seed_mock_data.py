from database import db

def seed_mock_data():
    mock_players = [
        {"id": "p1", "name": "Patrick Mahomes", "position": "QB", "team": "Kansas City Chiefs", "status": "ACT", "jersey": "15"},
        {"id": "p2", "name": "Travis Kelce", "position": "TE", "team": "Kansas City Chiefs", "status": "ACT", "jersey": "87"},
        {"id": "p3", "name": "Justin Jefferson", "position": "WR", "team": "Minnesota Vikings", "status": "ACT", "jersey": "18"},
        {"id": "p4", "name": "Christian McCaffrey", "position": "RB", "team": "San Francisco 49ers", "status": "ACT", "jersey": "23"},
        {"id": "p5", "name": "Tyreek Hill", "position": "WR", "team": "Miami Dolphins", "status": "ACT", "jersey": "10"},
        {"id": "p6", "name": "Lamar Jackson", "position": "QB", "team": "Baltimore Ravens", "status": "ACT", "jersey": "8"},
        {"id": "p7", "name": "Derrick Henry", "position": "RB", "team": "Baltimore Ravens", "status": "ACT", "jersey": "22"},
        {"id": "p8", "name": "A.J. Brown", "position": "WR", "team": "Philadelphia Eagles", "status": "ACT", "jersey": "11"},
        {"id": "p9", "name": "Josh Allen", "position": "QB", "team": "Buffalo Bills", "status": "ACT", "jersey": "17"},
        {"id": "p10", "name": "Stefon Diggs", "position": "WR", "team": "Houston Texans", "status": "ACT", "jersey": "1"},
    ]

    for player in mock_players:
        db.add_player_to_db(player)
    
    print(f"Seeded {len(mock_players)} mock players into the database.")

if __name__ == "__main__":
    seed_mock_data()
