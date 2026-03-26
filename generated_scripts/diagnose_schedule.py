from database import Database

def diagnose():
    db = Database()
    teams = list(db.db.nfl_teams.find({"name": {"$ne": "TBD"}, "id": {"$ne": None}}))
    team_names = {}
    for t in teams:
        team_names[t['id']] = f"{t['market']} {t['name']}"
    
    schedule = list(db.db.nfl_schedule.find())
    
    week_counts = {t_id: {wk: 0 for wk in range(1, 19)} for t_id in team_names}
    
    for game in schedule:
        h_id = game['home']['id']
        a_id = game['away']['id']
        wk = game['week_number']
        if h_id in week_counts:
            week_counts[h_id][wk] += 1
        if a_id in week_counts:
            week_counts[a_id][wk] += 1
            
    print("--- Schedule Diagnosis ---")
    bad_teams = 0
    for t_id, wks in week_counts.items():
        byes = [wk for wk, count in wks.items() if count == 0]
        multi_game_weeks = [wk for wk, count in wks.items() if count > 1]
        
        if len(byes) != 1 or multi_game_weeks:
            bad_teams += 1
            print(f"Team: {team_names[t_id]}")
            print(f"  Byes: {byes}")
            if multi_game_weeks:
                print(f"  Multi-game weeks: {multi_game_weeks}")
    
    if bad_teams == 0:
        print("All teams have exactly 1 bye and no multi-game weeks.")
    else:
        print(f"Found issues with {bad_teams} teams.")

if __name__ == "__main__":
    diagnose()
