import random
from database import Database
from pymongo import UpdateOne

def simulate_season():
    db = Database()
    print("Fetching players and teams...")
    all_players = list(db.players.find())
    nfl_teams = list(db.db.nfl_teams.find())
    name_to_full = {t['name']: f"{t['market']} {t['name']}" for t in nfl_teams}
    
    # 1. Tier Distribution (Optimized for actual player counts)
    by_pos = {"QB": [], "RB": [], "WR": [], "TE": [], "K": [], "FB": []}
    for p in all_players:
        pos = p.get('position')
        if pos in by_pos:
            by_pos[pos].append(p)
            p['tier'] = 'Depth'

    # Combine RB and FB into one pool for backfield logic
    backfield_pool = by_pos["RB"] + by_pos["FB"]
    random.shuffle(backfield_pool)

    # Scarcity configuration
    scarcity = {
        "QB": {"Elite": 4, "Star": 12, "Starter": 20},
        "WR": {"Elite": 8, "Star": 25, "Starter": 45},
        "TE": {"Elite": 4, "Star": 10, "Starter": 25}
    }
    
    # Backfield specific (Total 131)
    # Elite(2) + Star(15) + Starter(32) + Role(60) = 109 active. 22 reserves.
    backfield_scarcity = {"Elite": 2, "Star": 15, "Starter": 32, "Role": 60}

    # Assign tiers for all positions EXCEPT backfield
    for pos, counts in scarcity.items():
        players = by_pos[pos]
        random.shuffle(players)
        for tier, count in counts.items():
            for _ in range(min(count, len(players))):
                players.pop().update({'tier': tier})

    # Assign tiers for backfield specifically
    for tier, count in backfield_scarcity.items():
        for _ in range(min(count, len(backfield_pool))):
            backfield_pool.pop().update({'tier': tier})

    teams_dict = {}
    for p in all_players:
        team = p.get('team')
        if team not in teams_dict:
            teams_dict[team] = {"QB": [], "RB": [], "WR": [], "TE": [], "K": [], "FB": []}
        pos = p.get('position')
        if pos in teams_dict[team]:
            teams_dict[team][pos].append(p)

    profiles = {
        "QB": {
            "Elite":   {"yds": (270, 310), "att": (34, 40), "comp_p": (0.66, 0.72), "td_range": [2, 2, 3, 3]},
            "Star":    {"yds": (210, 250), "att": (30, 36), "comp_p": (0.62, 0.68), "td_range": [1, 2, 2]},
            "Starter": {"yds": (170, 210), "att": (26, 32), "comp_p": (0.58, 0.64), "td_range": [1, 1, 2]},
            "Depth":   {"yds": (10, 30), "att": (2, 6), "comp_p": (0.5, 0.6), "td_range": [0, 0, 1], "chance": 0.2}
        },
        "WR": {
            "Elite": {"yds": (75, 110), "rec": (6, 9), "td_prob": 0.6},
            "Star": {"yds": (50, 80), "rec": (4, 7), "td_prob": 0.4},
            "Starter": {"yds": (30, 55), "rec": (2, 5), "td_prob": 0.2},
            "Depth": {"yds": (10, 30), "rec": (1, 3), "td_prob": 0.05, "chance": 0.8}
        },
        "TE": {
            "Elite": {"yds": (60, 90), "rec": (5, 8), "td_prob": 0.45},
            "Star": {"yds": (35, 60), "rec": (3, 5), "td_prob": 0.25},
            "Starter": {"yds": (15, 35), "rec": (1, 3), "td_prob": 0.1},
            "Depth": {"yds": (5, 20), "rec": (1, 2), "td_prob": 0.02, "chance": 0.8}
        },
        "BACKFIELD": { # Shared for RB/FB
            "Elite": {"rush_yds": (85, 100), "rush_att": (18, 22), "rec_yds": (10, 25), "rec": (2, 4), "td_prob": 0.7},
            "Star": {"rush_yds": (50, 75), "rush_att": (12, 18), "rec_yds": (5, 15), "rec": (1, 3), "td_prob": 0.4},
            "Starter": {"rush_yds": (25, 45), "rush_att": (6, 12), "rec_yds": (0, 8), "rec": (0, 2), "td_prob": 0.2},
            "Role": {"rush_yds": (5, 15), "rush_att": (2, 6), "rec_yds": (0, 5), "rec": (0, 1), "td_prob": 0.05, "chance": 0.9},
            "Depth": {"rush_yds": (0, 5), "rush_att": (0, 2), "rec_yds": (0, 2), "rec": (0, 1), "td_prob": 0.01, "chance": 0.1}
        }
    }

    games = list(db.db.nfl_games.find())
    print(f"Simulating 272 games with Optimized Backfield Distribution...")
    bulk_updates = []

    for game in games:
        h_id, a_id = game['statistics']['home']['id'], game['statistics']['away']['id']
        h_full_name = f"{db.db.nfl_teams.find_one({'id': h_id})['market']} {db.db.nfl_teams.find_one({'id': h_id})['name']}"
        a_full_name = f"{db.db.nfl_teams.find_one({'id': a_id})['market']} {db.db.nfl_teams.find_one({'id': a_id})['name']}"

        game_stats = {"home": {"id": h_id, "passing": {"players": []}, "rushing": {"players": []}, "receiving": {"players": []}},
                      "away": {"id": a_id, "passing": {"players": []}, "rushing": {"players": []}, "receiving": {"players": []}}}
        
        for side, team_name in [("home", h_full_name), ("away", a_full_name)]:
            if team_name not in teams_dict: continue
            roster = teams_dict[team_name]
            qbs = sorted(roster.get('QB', []), key=lambda x: ['Elite', 'Star', 'Starter', 'Depth'].index(x['tier']))
            if not qbs: continue
            
            qb = qbs[0]; q_prof = profiles['QB'][qb['tier']]
            q_att = random.randint(*q_prof['att']); q_comp = int(q_att * random.uniform(*q_prof['comp_p'])); q_yds = random.randint(*q_prof['yds']); q_tds = random.choice(q_prof['td_range'])
            game_stats[side]['passing']['players'].append({"id": qb['id'], "name": qb['name'], "position": "QB", "attempts": q_att, "completions": q_comp, "yards": q_yds, "touchdowns": q_tds, "interceptions": random.choice([0, 0, 1]), "fumbles_lost": 0})
            
            rem_yds, rem_tds, rem_comp = q_yds, q_tds, q_comp
            
            # Combine skill for receiving pool
            skill_receivers = roster.get('WR', []) + roster.get('TE', []) + roster.get('RB', []) + roster.get('FB', [])
            random.shuffle(skill_receivers)

            for p in skill_receivers:
                pos = p['position']; tier = p['tier']
                # Determine profile
                if pos in ['RB', 'FB']:
                    prof = profiles['BACKFIELD'].get(tier, profiles['BACKFIELD']['Depth'])
                else:
                    prof = profiles[pos].get(tier, profiles[pos]['Depth'])
                
                # Chance to participate (Depth/Role)
                if tier in ['Depth', 'Role'] and random.random() > prof.get('chance', 1.0): continue
                
                # Rushing (Only Backfield)
                if pos in ['RB', 'FB']:
                    r_att = random.randint(*prof['rush_att']); r_yds = random.randint(*prof['rush_yds'])
                    r_tds = 1 if random.random() < prof['td_prob'] else 0
                    game_stats[side]['rushing']['players'].append({"id": p['id'], "name": p['name'], "position": pos, "attempts": r_att, "yards": r_yds, "touchdowns": r_tds, "fumbles_lost": 0})
                
                # Receiving
                p_rec = min(rem_comp, random.randint(*prof.get('rec', (1, 2))))
                p_yds = min(rem_yds, random.randint(*prof.get('yds', (5, 15)) if 'yds' in prof else prof.get('rec_yds', (5, 10)))) if p_rec > 0 else 0
                p_tds = 1 if rem_tds > 0 and random.random() < prof.get('td_prob', 0.1) else 0
                if p_rec > 0 or p_tds > 0:
                    game_stats[side]['receiving']['players'].append({"id": p['id'], "name": p['name'], "position": pos, "receptions": p_rec, "yards": p_yds, "touchdowns": p_tds, "fumbles_lost": 0})
                    rem_yds -= p_yds; rem_tds -= p_tds; rem_comp -= p_rec

        bulk_updates.append(UpdateOne({"id": game["id"]}, {"$set": {"statistics": game_stats, "summary.home.points": random.randint(14, 38), "summary.away.points": random.randint(14, 38)}}))

    if bulk_updates:
        db.db.nfl_games.bulk_write(bulk_updates)
        print(f"Successfully re-simulated with Optimized 131-player backfield logic.")

if __name__ == "__main__":
    simulate_season()
