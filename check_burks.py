from database import Database

def check_burks_stats():
    db = Database()
    p_id = '45763342-0208-46ab-a5d2-6c6e4ff66b66'
    games = list(db.nfl_games.find({"summary.season.year": 2026}))
    total_tds = 0
    print(f"Checking 2026 games for Burks (ID: {p_id})")
    for g in games:
        stats = g.get('statistics', {})
        for side in ['home', 'away']:
            side_stats = stats.get(side, {})
            for cat in ['passing', 'rushing', 'receiving']:
                for p in side_stats.get(cat, {}).get('players', []):
                    if p['id'] == p_id:
                        td = p.get('touchdowns', 0)
                        if td > 0:
                            print(f"Game {g['id']} (Week {g['summary']['week']['sequence']}): {td} {cat} TD(s)")
                            total_tds += td
    print(f"Total TDs found: {total_tds}")

if __name__ == '__main__':
    check_burks_stats()
