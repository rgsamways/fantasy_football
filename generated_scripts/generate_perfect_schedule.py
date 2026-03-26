import uuid
import random
from database import Database

def generate_perfect_schedule():
    db = Database()
    
    # 1. Teams
    raw_teams = list(db.db.nfl_teams.find())
    teams_dict = {t['id']: t for t in raw_teams}
    team_ids = list(teams_dict.keys())
    
    # 2. Divide teams into 8 Groups of 4 (Bye Groups)
    shuffled_ids = list(team_ids)
    random.shuffle(shuffled_ids)
    bye_groups = {wk: shuffled_ids[(wk-6)*4 : (wk-5)*4] for wk in range(6, 14)}

    # 3. Build Round Robin Rounds
    # But we MUST ensure that in Round X, the teams in ByeGroup X 
    # are paired WITH EACH OTHER.
    def get_custom_round(bye_teams, other_teams):
        matches = []
        # Pair bye teams together (2 games)
        bt = list(bye_teams)
        matches.append((bt[0], bt[1]))
        matches.append((bt[2], bt[3]))
        
        # Pair the other 28 teams together (14 games) using standard RR logic
        ot = list(other_teams)
        n = len(ot)
        for i in range(n // 2):
            matches.append((ot[i], ot[n - 1 - i]))
        return matches

    final_schedule = {wk: [] for wk in range(1, 19)}
    
    # Generate 17 distinct rounds
    # For rounds 6-13, we use our custom "pair-bye-teams-together" logic
    for wk in range(1, 18):
        if 6 <= wk <= 13:
            bt = bye_groups[wk]
            ot = [t for t in team_ids if t not in bt]
            # Shuffle other teams each week so matchups aren't identical
            random.shuffle(ot)
            matches = get_custom_round(bt, ot)
            
            # The 2 bye-team games move to week 18
            final_schedule[18].append(matches.pop(0))
            final_schedule[18].append(matches.pop(0))
            # The other 14 games stay in the week
            final_schedule[wk] = matches
        else:
            # Standard week (no byes) - 16 games
            pool = list(team_ids)
            random.shuffle(pool)
            for i in range(16):
                final_schedule[wk].append((pool[i], pool[31-i]))

    # 5. DB Insertion
    db_schedule = []
    db_games = []
    for wk, games in final_schedule.items():
        for h_id, a_id in games:
            h, a = teams_dict[h_id], teams_dict[a_id]
            g_id = str(uuid.uuid4())
            common = {"id": g_id, "week_number": wk, "week_title": str(wk), "season_year": 2024,
                      "home": {"id": h_id, "name": f"{h['market']} {h['name']}", "alias": h['alias']},
                      "away": {"id": a_id, "name": f"{a['market']} {a['name']}", "alias": a['alias']}}
            db_schedule.append({**common, "week_id": str(uuid.uuid4()), "status": "scheduled", "scoring": {"home_points": 0, "away_points": 0}})
            db_games.append({
                "id": g_id,
                "summary": {
                    "season": {"year": 2024, "type": "REG"}, "week": {"sequence": wk, "title": str(wk)},
                    "home": {"id": h_id, "name": h['name'], "points": 0}, "away": {"id": a_id, "name": a['name'], "points": 0}
                },
                "statistics": {
                    "home": {"id": h_id, "passing": {"players": []}, "rushing": {"players": []}, "receiving": {"players": []}},
                    "away": {"id": a_id, "passing": {"players": []}, "rushing": {"players": []}, "receiving": {"players": []}}
                }
            })

    db.db.nfl_schedule.delete_many({})
    db.db.nfl_games.delete_many({})
    db.db.nfl_schedule.insert_many(db_schedule)
    db.db.nfl_games.insert_many(db_games)
    print("Perfect 18-Week Schedule Rebuilt using Matchup-Locked Byes.")

if __name__ == "__main__":
    generate_perfect_schedule()
