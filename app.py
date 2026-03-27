import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from database import db
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "yoursecretkeyforflasksessions")

def create_app():
    return app

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')

        if db.get_user(username):
            flash("Username already exists.", "error")
            return redirect(url_for('register'))

        db.create_user(username, password, email)
        flash("Registration successful. Please login.", "success")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = db.get_user(username)
        if user and db.verify_password(password, user['password']):
            session['user_id'] = str(user['_id'])
            session['username'] = user['username']
            session['is_site_admin'] = user.get('is_site_admin', False)
            session['is_god'] = user.get('is_god', False)
            return redirect(url_for('leagues'))
        else:
            flash("Invalid username or password.", "error")
            return redirect(url_for('login'))
    return render_template('login.html')

def calculate_fantasy_points(player_id, league_id=None):
    """Calculates fantasy points for a player based on Week 1 stats and league scoring settings."""
    # Fetch scoring settings from the league, or use defaults
    settings = db.get_league_scoring_settings(league_id)
    
    pass_settings = settings.get('passing', {})
    rush_settings = settings.get('rushing', {})
    rec_settings = settings.get('receiving', {})
    misc_settings = settings.get('misc', {})

    # Fetch all games
    all_games = list(db.db.nfl_games.find())
    total_points = 0.0

    for game in all_games:
        stats = game.get('statistics', {})

        # Search in both home and away statistics
        for side in ['home', 'away']:
            side_stats = stats.get(side, {})
            
            # Passing
            passing_players = side_stats.get('passing', {}).get('players', [])
            for p in passing_players:
                if p.get('id') == player_id:
                    total_points += p.get('touchdowns', 0) * pass_settings.get('td', 0)
                    total_points += p.get('yards', 0) * pass_settings.get('yard', 0)
                    total_points += p.get('attempts', 0) * pass_settings.get('attempt', 0)
                    total_points += p.get('completions', 0) * pass_settings.get('completion', 0)
                    total_points += p.get('interceptions', 0) * pass_settings.get('interception', 0)

            # Rushing
            rushing_players = side_stats.get('rushing', {}).get('players', [])
            for p in rushing_players:
                if p.get('id') == player_id:
                    total_points += p.get('touchdowns', 0) * rush_settings.get('td', 0)
                    total_points += p.get('yards', 0) * rush_settings.get('yard', 0)
                    total_points += p.get('attempts', 0) * rush_settings.get('attempt', 0)

            # Receiving
            receiving_players = side_stats.get('receiving', {}).get('players', [])
            for p in receiving_players:
                if p.get('id') == player_id:
                    total_points += p.get('touchdowns', 0) * rec_settings.get('td', 0)
                    total_points += p.get('yards', 0) * rec_settings.get('yard', 0)
                    total_points += p.get('receptions', 0) * rec_settings.get('reception', 0)

            # Fumbles
            for p in passing_players + rushing_players + receiving_players:
                if p.get('id') == player_id:
                    # Deduct fumbles once per player per game, even if they appear in multiple categories
                    # (Though usually they're only in one category or have fumbles in one)
                    # To be safe, we'll track if we already counted fumbles for this player in this side/game
                    pass # We'll use a better approach below
            
            # Refined Fumble/Category-independent check
            # We'll collect all unique players on this side and check their fumbles
            seen_player_ids = set()
            for cat in ['passing', 'rushing', 'receiving']:
                for p in side_stats.get(cat, {}).get('players', []):
                    if p.get('id') == player_id and player_id not in seen_player_ids:
                        total_points += p.get('fumbles_lost', 0) * misc_settings.get('fumble_lost', 0)
                        seen_player_ids.add(player_id)

    return round(total_points, 2)

def get_all_player_points(league_id=None):
    """Optimized: Calculates points for ALL players in a single pass over the game data."""
    settings = db.get_league_scoring_settings(league_id)
    pass_s = settings.get('passing', {})
    rush_s = settings.get('rushing', {})
    rec_s = settings.get('receiving', {})
    misc_s = settings.get('misc', {})

    # The lookup table
    player_points = {} # { player_id: float }

    # Fetch ALL games once
    all_games = list(db.db.nfl_games.find({}, {"statistics": 1}))
    
    for game in all_games:
        stats = game.get('statistics', {})
        for side in ['home', 'away']:
            side_stats = stats.get(side, {})
            
            # Use a seen set per game to handle the fumble deduction logic correctly
            game_seen_ids = set()

            # Passing
            for p in side_stats.get('passing', {}).get('players', []):
                p_id = p['id']
                pts = (p.get('touchdowns', 0) * pass_s.get('td', 0) +
                       p.get('yards', 0) * pass_s.get('yard', 0) +
                       p.get('attempts', 0) * pass_s.get('attempt', 0) +
                       p.get('completions', 0) * pass_s.get('completion', 0) +
                       p.get('interceptions', 0) * pass_s.get('interception', 0))
                
                player_points[p_id] = player_points.get(p_id, 0.0) + pts
                
                if p_id not in game_seen_ids:
                    player_points[p_id] += p.get('fumbles_lost', 0) * misc_s.get('fumble_lost', 0)
                    game_seen_ids.add(p_id)

            # Rushing
            for p in side_stats.get('rushing', {}).get('players', []):
                p_id = p['id']
                pts = (p.get('touchdowns', 0) * rush_s.get('td', 0) +
                       p.get('yards', 0) * rush_s.get('yard', 0) +
                       p.get('attempts', 0) * rush_s.get('attempt', 0))
                
                player_points[p_id] = player_points.get(p_id, 0.0) + pts
                
                if p_id not in game_seen_ids:
                    player_points[p_id] += p.get('fumbles_lost', 0) * misc_s.get('fumble_lost', 0)
                    game_seen_ids.add(p_id)

            # Receiving
            for p in side_stats.get('receiving', {}).get('players', []):
                p_id = p['id']
                pts = (p.get('touchdowns', 0) * rec_s.get('td', 0) +
                       p.get('yards', 0) * rec_s.get('yard', 0) +
                       p.get('receptions', 0) * rec_s.get('reception', 0))
                
                player_points[p_id] = player_points.get(p_id, 0.0) + pts
                
                if p_id not in game_seen_ids:
                    player_points[p_id] += p.get('fumbles_lost', 0) * misc_s.get('fumble_lost', 0)
                    game_seen_ids.add(p_id)

    # Round all values
    return {p_id: round(pts, 2) for p_id, pts in player_points.items()}

def get_all_player_stats():
    """Optimized: Aggregates full season stats for ALL players in a single pass."""
    stats_lookup = {} # { player_id: { pass_yds, pass_td, rush_yds, rush_td, rec, rec_yds, rec_td, fumbles } }

    # Fetch ALL games once
    all_games = list(db.db.nfl_games.find({}, {"statistics": 1}))
    
    for game in all_games:
        stats = game.get('statistics', {})
        for side in ['home', 'away']:
            side_stats = stats.get(side, {})
            
            # Helper to init player in lookup
            def init_p(p_id):
                if p_id not in stats_lookup:
                    stats_lookup[p_id] = {
                        "pass_yds": 0, "pass_td": 0, "ints": 0,
                        "pass_att": 0, "pass_comp": 0,
                        "rush_yds": 0, "rush_td": 0, "rush_att": 0,
                        "receptions": 0, "rec_yds": 0, "rec_td": 0,
                        "fumbles": 0
                    }

            # Passing
            for p in side_stats.get('passing', {}).get('players', []):
                p_id = p['id']
                init_p(p_id)
                stats_lookup[p_id]["pass_yds"] += p.get('yards', 0)
                stats_lookup[p_id]["pass_td"] += p.get('touchdowns', 0)
                stats_lookup[p_id]["ints"] += p.get('interceptions', 0)
                stats_lookup[p_id]["pass_att"] += p.get('attempts', 0)
                stats_lookup[p_id]["pass_comp"] += p.get('completions', 0)
                stats_lookup[p_id]["fumbles"] += p.get('fumbles_lost', 0)

            # Rushing
            for p in side_stats.get('rushing', {}).get('players', []):
                p_id = p['id']
                init_p(p_id)
                stats_lookup[p_id]["rush_yds"] += p.get('yards', 0)
                stats_lookup[p_id]["rush_td"] += p.get('touchdowns', 0)
                stats_lookup[p_id]["rush_att"] += p.get('attempts', 0)
                stats_lookup[p_id]["fumbles"] += p.get('fumbles_lost', 0)

            # Receiving
            for p in side_stats.get('receiving', {}).get('players', []):
                p_id = p['id']
                init_p(p_id)
                stats_lookup[p_id]["receptions"] += p.get('receptions', 0)
                stats_lookup[p_id]["rec_yds"] += p.get('yards', 0)
                stats_lookup[p_id]["rec_td"] += p.get('touchdowns', 0)
                stats_lookup[p_id]["fumbles"] += p.get('fumbles_lost', 0)

    return stats_lookup

def get_all_player_data(league_id=None, season=None, week=None):
    """Ultra-Optimized: Aggregates stats AND calculates points for ALL players in ONE pass."""
    # 1. Determine the season to calculate for (ALWAYS use global site season)
    if not season:
        site_settings = db.get_site_settings()
        season = site_settings.get('current_season', 2025)

    settings = db.get_league_scoring_settings(league_id)
    pass_s = settings.get('passing', {})
    rush_s = settings.get('rushing', {})
    rec_s = settings.get('receiving', {})
    misc_s = settings.get('misc', {})

    # Single lookup table for everything
    player_data = {} # { player_id: { stats..., points } }

    # Fetch games for the TARGET season, optionally filtered to a specific week
    game_query = {"summary.season.year": season}
    if week is not None:
        game_query["summary.week.sequence"] = int(week)
    all_games = list(db.db.nfl_games.find(game_query, {"statistics": 1}))

    # If no games found for target season, fall back to the most recent season with data
    if not all_games:
        available = db.db.nfl_games.distinct("summary.season.year")
        if available:
            fallback = max(available)
            game_query["summary.season.year"] = fallback
            all_games = list(db.db.nfl_games.find(game_query, {"statistics": 1}))
    
    for game in all_games:
        stats = game.get('statistics', {})
        for side in ['home', 'away']:
            side_stats = stats.get(side, {})
            game_seen_ids = set()

            # Helper to init
            def get_p(p_id):
                if p_id not in player_data:
                    player_data[p_id] = {
                        "pass_yds": 0, "pass_td": 0, "ints": 0, "pass_att": 0, "pass_comp": 0,
                        "rush_yds": 0, "rush_td": 0, "rush_att": 0,
                        "receptions": 0, "rec_yds": 0, "rec_td": 0,
                        "fumbles": 0, "points": 0.0
                    }
                return player_data[p_id]

            # Passing
            for p in side_stats.get('passing', {}).get('players', []):
                p_id = p['id']
                pd = get_p(p_id)
                pd["pass_yds"] += p.get('yards', 0)
                pd["pass_td"] += p.get('touchdowns', 0)
                pd["ints"] += p.get('interceptions', 0)
                pd["pass_att"] += p.get('attempts', 0)
                pd["pass_comp"] += p.get('completions', 0)
                
                # Point Calc
                try:
                    term_pass = (p.get('touchdowns', 0) * pass_s.get('td', 0) +
                                 p.get('yards', 0) * pass_s.get('yard', 0) +
                                 p.get('attempts', 0) * pass_s.get('attempt', 0) +
                                 p.get('completions', 0) * pass_s.get('completion', 0) +
                                 p.get('interceptions', 0) * pass_s.get('interception', 0))
                    pd["points"] += term_pass
                except TypeError as e:
                    print(f"DEBUG ERROR PASSING: pd['points']={pd['points']} (type {type(pd['points'])}), p={p}, pass_s={pass_s}")
                    raise e
                
                if p_id not in game_seen_ids:
                    pd["fumbles"] += p.get('fumbles_lost', 0)
                    try:
                        term_fumble = p.get('fumbles_lost', 0) * misc_s.get('fumble_lost', 0)
                        pd["points"] += term_fumble
                    except TypeError as e:
                        print(f"DEBUG ERROR FUMBLE: pd['points']={pd['points']} (type {type(pd['points'])}), p={p}, misc_s={misc_s}")
                        raise e
                    game_seen_ids.add(p_id)

            # Rushing
            for p in side_stats.get('rushing', {}).get('players', []):
                p_id = p['id']
                pd = get_p(p_id)
                pd["rush_yds"] += p.get('yards', 0)
                pd["rush_td"] += p.get('touchdowns', 0)
                pd["rush_att"] += p.get('attempts', 0)
                
                # Point Calc
                try:
                    term_rush = (p.get('touchdowns', 0) * rush_s.get('td', 0) +
                                 p.get('yards', 0) * rush_s.get('yard', 0) +
                                 p.get('attempts', 0) * rush_s.get('attempt', 0))
                    pd["points"] += term_rush
                except TypeError as e:
                    print(f"DEBUG ERROR RUSHING: pd['points']={pd['points']} (type {type(pd['points'])}), p={p}, rush_s={rush_s}")
                    raise e
                
                if p_id not in game_seen_ids:
                    pd["fumbles"] += p.get('fumbles_lost', 0)
                    try:
                        term_fumble = p.get('fumbles_lost', 0) * misc_s.get('fumble_lost', 0)
                        pd["points"] += term_fumble
                    except TypeError as e:
                        print(f"DEBUG ERROR RUSH FUMBLE: pd['points']={pd['points']} (type {type(pd['points'])}), p={p}, misc_s={misc_s}")
                        raise e
                    game_seen_ids.add(p_id)

            # Receiving
            for p in side_stats.get('receiving', {}).get('players', []):
                p_id = p['id']
                pd = get_p(p_id)
                pd["receptions"] += p.get('receptions', 0)
                pd["rec_yds"] += p.get('yards', 0)
                pd["rec_td"] += p.get('touchdowns', 0)
                
                # Point Calc
                try:
                    term_rec = (p.get('touchdowns', 0) * rec_s.get('td', 0) +
                                 p.get('yards', 0) * rec_s.get('yard', 0) +
                                 p.get('receptions', 0) * rec_s.get('reception', 0))
                    pd["points"] += term_rec
                except TypeError as e:
                    print(f"DEBUG ERROR RECEIVING: pd['points']={pd['points']} (type {type(pd['points'])}), p={p}, rec_s={rec_s}")
                    raise e
                
                if p_id not in game_seen_ids:
                    pd["fumbles"] += p.get('fumbles_lost', 0)
                    try:
                        term_fumble = p.get('fumbles_lost', 0) * misc_s.get('fumble_lost', 0)
                        pd["points"] += term_fumble
                    except TypeError as e:
                        print(f"DEBUG ERROR REC FUMBLE: pd['points']={pd['points']} (type {type(pd['points'])}), p={p}, misc_s={misc_s}")
                        raise e
                    game_seen_ids.add(p_id)

    # Round points
    for p_id in player_data:
        player_data[p_id]["points"] = round(player_data[p_id]["points"], 2)
        
    return player_data

def calculate_salary(player_stats, salary_settings, position="QB"):
    """Calculates a player's salary based on the selected league model."""
    model = salary_settings.get('active_model', 'none')
    if model == 'none':
        return 0

    points = player_stats.get('points', 0.0)
    tds = player_stats.get('pass_td', 0) + player_stats.get('rush_td', 0) + player_stats.get('rec_td', 0)
    
    if model == 'points':
        # Direct points * multiplier
        multiplier = salary_settings.get('point_multiplier', 100000)
        return max(salary_settings.get('base_salary', 500000), points * multiplier)

    if model == 'touchdowns':
        # TDs * value, K capped at 100k
        if position == 'K':
            return 100000
        td_val = salary_settings.get('td_value', 100000)
        return max(salary_settings.get('base_salary', 500000), tds * td_val)

    if model == 'performance_floor':
        # Base + (Points over Avg * Multiplier)
        # Simplified for prototype: use 100 as "average"
        avg_pts = 100.0
        bonus = max(0, (points - avg_pts)) * salary_settings.get('point_multiplier', 50000)
        return salary_settings.get('base_salary', 500000) + bonus

    if model == 'nfl_mirror':
        # Real world cap hit (Requires external data or mock)
        # Mocking for now: use points * factor
        return points * 250000

    if model == 'tiered':
        # Fixed price based on position and rank
        # Simplified: Tier 1 (Points > 200), Tier 2 (100-200), Tier 3 (<100)
        if points > 250: return 25000000
        if points > 150: return 15000000
        if points > 50: return 5000000
        return salary_settings.get('base_salary', 500000)

    return 0

# --- Helper functions to be moved ---
def get_league_context(league_id):
    league = db.get_league(league_id)
    if not league:
        return None, None
    
    is_admin = False
    current_user_id = session.get('user_id')
    if current_user_id and current_user_id in league.get('administrators', []):
        is_admin = True
    
    return league, is_admin

def get_league_roster_slots(league):
    """Generates specific slots (e.g. 'RB1', 'RB2') from roster_settings."""
    settings = league.get('roster_settings', [])
    if not settings:
        # Fallback to current standard
        return ["QB", "RB1", "RB2", "WR1", "WR2", "TE", "FLEX", "K"]
    
    slots = []
    for group in settings:
        name = group['name']
        count = group['count']
        if count == 1:
            slots.append(name)
        else:
            for i in range(1, count + 1):
                slots.append(f"{name}{i}")
    return slots
# --- End of functions to be moved ---

@app.route('/api/award_achievement', methods=['POST'])
def api_award_achievement():
    if 'user_id' not in session:
        return {"success": False}, 401
    achievement_id = request.json.get('achievement_id')
    if not achievement_id:
        return {"success": False}, 400
    # Only allow client-side awardable achievements
    allowed = {'pull_the_shades_down', 'team_spirit'}
    if achievement_id not in allowed:
        return {"success": False, "message": "Not allowed"}, 403
    db.award_achievement(session['user_id'], achievement_id)
    return {"success": True}

@app.route('/api/team_colors')
def api_team_colors():
    teams = list(db.nfl_teams.find({"team_colors": {"$exists": True, "$ne": []}}, {"alias": 1, "market": 1, "name": 1, "team_colors": 1}))
    result = {}
    for t in teams:
        alias = t.get('alias')
        if not alias: continue
        primary = next((c['hex_color'] for c in t.get('team_colors', []) if c['type'] == 'primary'), None)
        secondary = next((c['hex_color'] for c in t.get('team_colors', []) if c['type'] == 'secondary'), None)
        if primary and secondary:
            result[alias] = {
                "name": f"{t['market']} {t['name']}",
                "primary": primary,
                "secondary": secondary
            }
    return result

@app.route('/nfl')
def nfl():
    return redirect(url_for('nfl_home'))

@app.route('/nfl/home')
def nfl_home():
    return render_template('nfl_home.html', active_tab='home')

@app.route('/social')
def social_home():
    # Placeholder channels — replace with DB-backed channels when ready
    channels = [
        {'name': 'general', 'description': 'General fantasy football discussion', 'member_count': 0},
        {'name': 'trades', 'description': 'Trade talk and analysis', 'member_count': 0},
        {'name': 'waiver-wire', 'description': 'Waiver wire pickups and drops', 'member_count': 0},
        {'name': 'trash-talk', 'description': 'All the banter you can handle', 'member_count': 0},
    ]
    return render_template('social_home.html', active_tab='home', channels=channels)

@app.route('/nfl/teams')
def nfl_teams():
    teams = db.get_all_teams()
    conferences = {}
    for team in teams:
        conf = team.get('conference')
        div = team.get('division')
        if conf not in conferences:
            conferences[conf] = {}
        if div not in conferences[conf]:
            conferences[conf][div] = []
        conferences[conf][div].append(team)
    for conf in conferences:
        conferences[conf] = dict(sorted(conferences[conf].items()))
    return render_template('nfl_teams.html', conferences=conferences, active_tab='teams')

@app.route('/nfl/players')
def nfl_players():
    all_players = db.get_all_players()
    all_data = get_all_player_data(None)
    for player in all_players:
        p_id = player['id']
        pd = all_data.get(p_id, {})
        player['pass_yds'] = pd.get('pass_yds', 0)
        player['pass_td'] = pd.get('pass_td', 0)
        player['pass_att'] = pd.get('pass_att', 0)
        player['pass_comp'] = pd.get('pass_comp', 0)
        player['ints'] = pd.get('ints', 0)
        player['rush_yds'] = pd.get('rush_yds', 0)
        player['rush_td'] = pd.get('rush_td', 0)
        player['rush_att'] = pd.get('rush_att', 0)
        player['receptions'] = pd.get('receptions', 0)
        player['rec_yds'] = pd.get('rec_yds', 0)
        player['rec_td'] = pd.get('rec_td', 0)
        player['fumbles'] = pd.get('fumbles', 0)
        player['points'] = pd.get('points', 0.0)
    return render_template('nfl_players.html', players=all_players, active_tab='players')

@app.route('/nfl/player/<player_id>')
def nfl_player(player_id):
    player = db.get_player_by_id(player_id)
    if not player:
        flash("Player not found.", "error")
        return redirect(url_for('nfl_players'))
    return render_template('nfl_player.html', player=player, active_tab='players')

@app.route('/nfl/standings')
def nfl_standings():
    s_seasons = set(db.nfl_schedule.distinct("season_year"))
    g_seasons = set(db.db.nfl_games.distinct("summary.season.year"))
    available_seasons = sorted(list(s_seasons | g_seasons), reverse=True)
    if not available_seasons:
        available_seasons = [2025]
    site_settings = db.get_site_settings()
    default_season = site_settings.get('current_season', 2025)
    try:
        selected_season = int(request.args.get('season', default_season))
    except (ValueError, TypeError):
        selected_season = default_season
    all_games = list(db.db.nfl_games.find({"summary.season.year": selected_season}))
    all_teams = db.get_all_teams()
    standings = {}
    for t in all_teams:
        t_id = t.get('id')
        if not t_id or t.get('name') == 'TBD': continue
        standings[t_id] = {
            "name": f"{t.get('market', '')} {t.get('name', '')}",
            "alias": t.get('alias', ''),
            "conference": t.get('conference', ''),
            "division": t.get('division', ''),
            "wins": 0, "losses": 0, "ties": 0,
            "pts_for": 0, "pts_against": 0
        }
    for game in all_games:
        h_id = game['summary']['home']['id']
        a_id = game['summary']['away']['id']
        h_pts = game['summary']['home']['points']
        a_pts = game['summary']['away']['points']
        if h_id in standings and a_id in standings:
            standings[h_id]['pts_for'] += h_pts
            standings[h_id]['pts_against'] += a_pts
            standings[a_id]['pts_for'] += a_pts
            standings[a_id]['pts_against'] += h_pts
            if h_pts > a_pts:
                standings[h_id]['wins'] += 1
                standings[a_id]['losses'] += 1
            elif a_pts > h_pts:
                standings[a_id]['wins'] += 1
                standings[h_id]['losses'] += 1
            else:
                standings[h_id]['ties'] += 1
                standings[a_id]['ties'] += 1
    for t_id in standings:
        s = standings[t_id]
        total_games = s['wins'] + s['losses'] + s['ties']
        s['pct'] = (s['wins'] + (0.5 * s['ties'])) / total_games if total_games > 0 else 0.0
        s['diff'] = s['pts_for'] - s['pts_against']
    conferences = {}
    for t_id, data in standings.items():
        conf = data['conference']
        div = data['division']
        if not conf or not div: continue
        if conf not in conferences: conferences[conf] = {}
        if div not in conferences[conf]: conferences[conf][div] = []
        conferences[conf][div].append(data)
    for conf in conferences:
        for div in conferences[conf]:
            conferences[conf][div].sort(key=lambda x: (x['pct'], x['diff']), reverse=True)
        conferences[conf] = dict(sorted(conferences[conf].items()))
    return render_template('nfl_standings.html',
                           conferences=conferences,
                           selected_season=selected_season,
                           available_seasons=available_seasons,
                           active_tab='standings')

@app.route('/nfl/schedule')
def nfl_schedule():
    s_seasons = set(db.nfl_schedule.distinct("season_year"))
    g_seasons = set(db.db.nfl_games.distinct("summary.season.year"))
    available_seasons = sorted(list(s_seasons | g_seasons), reverse=True)
    if not available_seasons:
        available_seasons = [2025]
    site_settings = db.get_site_settings()
    default_season = site_settings.get('current_season', 2025)
    try:
        selected_season = int(request.args.get('season', default_season))
    except (ValueError, TypeError):
        selected_season = default_season
    schedule = list(db.nfl_schedule.find({"season_year": selected_season}).sort([("week_number", 1)]))
    all_teams = db.get_all_teams()
    real_teams_dict = {}
    for t in all_teams:
        t_id = t.get('id')
        if t_id and t.get('name') != 'TBD' and t.get('alias') != 'TBD':
            real_teams_dict[t_id] = f"{t['market']} {t['name']}"
    weeks = {wk: {"games": [], "byes": []} for wk in range(1, 19)}
    for game in schedule:
        wk_num = game.get('week_number')
        if wk_num in weeks:
            weeks[wk_num]["games"].append(game)
    for wk_num in range(1, 19):
        teams_playing = set()
        for g in weeks[wk_num]['games']:
            teams_playing.add(g['home']['id'])
            teams_playing.add(g['away']['id'])
        for t_id, t_name in real_teams_dict.items():
            if t_id not in teams_playing:
                weeks[wk_num]['byes'].append(t_name)
        weeks[wk_num]['byes'].sort()
    return render_template('nfl_schedule.html',
                           weeks=weeks,
                           selected_season=selected_season,
                           available_seasons=available_seasons,
                           active_tab='schedule')

@app.route('/nfl/game/<game_id>')
def nfl_game_details(game_id):
    game_info = db.db.nfl_games.find_one({"id": game_id})
    if not game_info:
        flash("Game details not found.", "error")
        return redirect(url_for('nfl_schedule'))
    return render_template('nfl_game_details.html', game=game_info, active_tab='schedule')

@app.route('/nfl/team/<team_alias>')
def nfl_team(team_alias):
    team_info = db.db.nfl_teams.find_one({"alias": team_alias})
    if not team_info:
        flash("Team not found.", "error")
        return redirect(url_for('nfl_teams'))
    full_team_name = f"{team_info['market']} {team_info['name']}"
    team_players = list(db.players.find({"team": full_team_name}))
    pos_order = {"QB": 0, "RB": 1, "FB": 2, "WR": 3, "TE": 4, "K": 5}
    team_players.sort(key=lambda x: pos_order.get(x.get('position'), 99))
    return render_template('nfl_team.html', team=team_info, players=team_players, active_tab='teams')

@app.route('/nfl/rumors')
def nfl_rumors():
    return render_template('nfl_rumors.html', active_tab='rumors')

@app.route('/admin')
def admin_panel():
    if not session.get('is_site_admin'):
        flash("Unauthorized access.", "error")
        return redirect(url_for('index'))

    user_count = db.users.count_documents({})
    league_count = db.leagues.count_documents({})
    player_count = db.players.count_documents({})

    return render_template('admin_dashboard.html',
                           user_count=user_count,
                           league_count=league_count,
                           player_count=player_count,
                           active_tab='dashboard')

@app.route('/admin/leagues')
def admin_leagues():
    if not session.get('is_site_admin'):
        flash("Unauthorized.", "error")
        return redirect(url_for('index'))
    all_leagues = list(db.leagues.find())
    archives = db.get_all_archives()
    archived_keys = [(a['league_id'], a['season']) for a in archives]
    return render_template('admin_leagues.html', all_leagues=all_leagues,
                           archives=archives, archived_keys=archived_keys,
                           active_tab='leagues')

@app.route('/admin/archive_league/<league_id>', methods=['POST'])
def admin_archive_league(league_id):
    if not session.get('is_site_admin'):
        flash("Unauthorized.", "error")
        return redirect(url_for('index'))

    league = db.get_league(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('admin_panel'))

    season = league.get('current_season', 2026)
    all_points = get_all_player_data(league_id)
    slots = get_league_roster_slots(league)
    all_matchups = db.get_all_league_matchups(league_id, season)

    standings = {}
    for u_id in league.get('user_ids', []):
        from bson import ObjectId
        user = db.users.find_one({"_id": ObjectId(u_id)})
        roster = db.get_roster(u_id, league_id)
        team_name = (roster.get('team', {}).get('name') if roster else None) or (user['username'] if user else 'Unknown')
        standings[u_id] = {'user_id': u_id, 'username': user['username'] if user else 'Unknown',
                           'team_name': team_name, 'wins': 0, 'losses': 0, 'ties': 0, 'points_for': 0.0}

    def _score(u_id, week=None):
        r = db.get_roster(u_id, league_id)
        if not r: return 0.0
        s_ids = r.get('starters', {})
        pts = get_all_player_data(league_id, week=week) if week else all_points
        return round(sum(pts.get(s_ids.get(sl), {}).get('points', 0.0) for sl in slots), 2)

    for m in all_matchups:
        h, a = m['home_id'], m['away_id']
        wk = m['week_number']
        hs, as_ = _score(h, wk), _score(a, wk)
        for uid, ms, os in [(h, hs, as_), (a, as_, hs)]:
            if uid in standings:
                standings[uid]['points_for'] += ms
                if ms > os: standings[uid]['wins'] += 1
                elif os > ms: standings[uid]['losses'] += 1
                else: standings[uid]['ties'] += 1
    for s in standings.values():
        s['points_for'] = round(s['points_for'], 2)

    final_rosters = []
    for u_id in league.get('user_ids', []):
        from bson import ObjectId
        user = db.users.find_one({"_id": ObjectId(u_id)})
        roster = db.get_roster(u_id, league_id)
        players = []
        for p_id in (roster.get('player_ids', []) if roster else []):
            p = db.get_player_by_id(p_id)
            if p:
                pd = all_points.get(p_id, {})
                players.append({'id': p_id, 'name': p.get('name'), 'position': p.get('position'),
                                 'team': p.get('team'), 'points': round(pd.get('points', 0.0), 2)})
        final_rosters.append({
            'user_id': u_id,
            'username': user['username'] if user else 'Unknown',
            'team_name': standings.get(u_id, {}).get('team_name', 'Unknown'),
            'players': players
        })

    schedule = [{'week': m['week_number'], 'home_id': m['home_id'], 'away_id': m['away_id'],
                 'home_score': _score(m['home_id'], m['week_number']), 'away_score': _score(m['away_id'], m['week_number'])}
                for m in sorted(all_matchups, key=lambda x: x['week_number'])]

    all_trades = db.get_league_trades(league_id)
    player_cache = {}
    def _pname(pid):
        if pid not in player_cache:
            p = db.get_player_by_id(pid)
            player_cache[pid] = p.get('name', 'Unknown') if p else 'Unknown'
        return player_cache[pid]

    trades = [{'date': (t.get('status_modified') or t['_id'].generation_time).isoformat(),
               'offering_team': standings.get(t['team_offering']['team_id'], {}).get('team_name', 'Unknown'),
               'responding_team': standings.get(t['team_responding']['team_id'], {}).get('team_name', 'Unknown'),
               'offering_players': [_pname(p) for p in t['team_offering'].get('player_ids', [])],
               'responding_players': [_pname(p) for p in t['team_responding'].get('player_ids', [])]}
              for t in all_trades if t['status'] == 'Finalized']

    db.archive_league(league_id, season, {
        "id": str(uuid.uuid4()),
        "league_id": league_id,
        "league_name": league['name'],
        "season": season,
        "standings": sorted(standings.values(), key=lambda x: (x['wins'], x['points_for']), reverse=True),
        "final_rosters": final_rosters,
        "schedule": schedule,
        "trades": trades,
        "waiver_claims": [c for c in db.get_waiver_claims(league_id) if c['status'] == 'Awarded'],
    })
    flash(f"League '{league['name']}' ({season}) archived.", "success")
    return redirect(url_for('admin_leagues'))

@app.route('/admin/users')
def manage_users():
    if not session.get('is_site_admin'):
        flash("Unauthorized access.", "error")
        return redirect(url_for('index'))
    
    users = list(db.users.find())
    return render_template('admin_users.html', users=users, active_tab='users')

@app.route('/admin/toggle_admin/<user_id>', methods=['POST'])
def toggle_admin(user_id):
    if not session.get('is_site_admin'):
        flash("Unauthorized access.", "error")
        return redirect(url_for('index'))
    
    user = db.get_user_by_id(user_id)
    if user:
        current_status = user.get('is_site_admin', False)
        
        # Safeguard: Don't let god remove admin from himself
        if user_id == session.get('user_id') and session.get('is_god'):
            flash("Safeguard: As a 'God' user, you cannot remove your own administrator status.", "error")
            return redirect(url_for('manage_users'))

        # Safeguard: Check if we are removing admin from the last admin
        if current_status:
            admin_count = db.users.count_documents({"is_site_admin": True})
            if admin_count <= 1:
                flash("Safeguard: You cannot remove the last site administrator.", "error")
                return redirect(url_for('manage_users'))

        new_status = not current_status
        db.set_site_admin(user_id, new_status)
        
        # Don't let the current user accidentally de-admin themselves without knowing
        if user_id == session.get('user_id'):
            session['is_site_admin'] = new_status
            
        flash(f"Updated admin status for {user['username']}.", "success")
    
    return redirect(url_for('manage_users'))

@app.route('/admin/data')
def admin_data():
    if not session.get('is_site_admin'):
        flash("Unauthorized access.", "error")
        return redirect(url_for('index'))
    
    # Fetch all games from nfl_games and determine available seasons
    all_games = list(db.db.nfl_games.find())
    available_seasons = sorted(list(set(game['summary']['season']['year'] for game in all_games if 'summary' in game and 'season' in game['summary'] and 'year' in game['summary']['season'])), reverse=True)
    
    # Default to the latest season if no season is selected or available_seasons is empty
    default_season = available_seasons[0] if available_seasons else 2025
    try:
        selected_season = int(request.args.get('season', default_season))
    except ValueError:
        selected_season = default_season

    # Filter games by the selected season
    season_games = [game for game in all_games if 'summary' in game and 'season' in game['summary'] and 'year' in game['summary']['season'] and game['summary']['season']['year'] == selected_season]
    
    # Group by week for display
    weeks = {}
    for game in season_games:
        wk_num = game.get('summary', {}).get('week', {}).get('sequence', 'Unknown')
        if wk_num not in weeks:
            weeks[wk_num] = []
        weeks[wk_num].append(game)
    
    sorted_weeks = dict(sorted(weeks.items()))
    return render_template('admin_data.html', weeks=sorted_weeks, active_tab='data', available_seasons=available_seasons, selected_season=selected_season)

@app.route('/admin/data/game/<game_id>', methods=['GET', 'POST'])
def admin_game_edit(game_id):
    if not session.get('is_site_admin'):
        flash("Unauthorized access.", "error")
        return redirect(url_for('index'))
    
    game = db.db.nfl_games.find_one({"id": game_id})
    if not game:
        flash("Game not found.", "error")
        return redirect(url_for('admin_data'))
        
    if request.method == 'POST':
        # Processing a massive form. We'll iterate through home/away and pass/rush/rec
        updated_stats = game.get('statistics', {})
        
        for side in ['home', 'away']:
            for category in ['passing', 'rushing', 'receiving']:
                players = updated_stats.get(side, {}).get(category, {}).get('players', [])
                for p in players:
                    p_id = p['id']
                    # Dynamically get fields based on category
                    if category == 'passing':
                        p['attempts'] = int(request.form.get(f"{side}_{p_id}_attempts", 0))
                        p['completions'] = int(request.form.get(f"{side}_{p_id}_completions", 0))
                        p['yards'] = int(request.form.get(f"{side}_{p_id}_yards", 0))
                        p['touchdowns'] = int(request.form.get(f"{side}_{p_id}_tds", 0))
                        p['interceptions'] = int(request.form.get(f"{side}_{p_id}_ints", 0))
                    elif category == 'rushing':
                        p['attempts'] = int(request.form.get(f"{side}_{p_id}_attempts", 0))
                        p['yards'] = int(request.form.get(f"{side}_{p_id}_yards", 0))
                        p['touchdowns'] = int(request.form.get(f"{side}_{p_id}_tds", 0))
                    elif category == 'receiving':
                        p['receptions'] = int(request.form.get(f"{side}_{p_id}_receptions", 0))
                        p['yards'] = int(request.form.get(f"{side}_{p_id}_yards", 0))
                        p['touchdowns'] = int(request.form.get(f"{side}_{p_id}_tds", 0))
                    
                    # Look for fumbles in any player object
                    p['fumbles_lost'] = int(request.form.get(f"{side}_{p_id}_fumbles", 0))

        db.db.nfl_games.update_one({"id": game_id}, {"$set": {"statistics": updated_stats}})

        # Recompute NFL game score from statistics
        # Passing TDs == Receiving TDs (same play), so only count rushing + receiving
        nfl_scores = {}
        for side in ['home', 'away']:
            side_stats = updated_stats.get(side, {})
            rush_tds = sum(p.get('touchdowns', 0) for p in side_stats.get('rushing', {}).get('players', []))
            rec_tds = sum(p.get('touchdowns', 0) for p in side_stats.get('receiving', {}).get('players', []))
            nfl_scores[f'summary.{side}.points'] = (rush_tds + rec_tds) * 6
        db.db.nfl_games.update_one({"id": game_id}, {"$set": nfl_scores})

        # Sync scores to nfl_schedule
        db.nfl_schedule.update_one(
            {"id": game_id},
            {"$set": {
                "scoring.home_points": nfl_scores["summary.home.points"],
                "scoring.away_points": nfl_scores["summary.away.points"],
                "status": "closed"
            }}
        )

        # Recompute and store scores on all affected fantasy matchups
        season = game.get('summary', {}).get('season', {}).get('year')
        week = game.get('summary', {}).get('week', {}).get('sequence')
        if season and week:
            all_leagues = list(db.leagues.find())
            for league in all_leagues:
                league_id = league['id']
                all_points = get_all_player_data(league_id, season=season, week=week)
                slots = get_league_roster_slots(league)
                # Fantasy matchups use the league's current_season, not the NFL game season
                fantasy_season = league.get('current_season', season)
                matchups = db.get_league_matchups(league_id, week, fantasy_season)
                for m in matchups:
                    for side, uid in [('home', m['home_id']), ('away', m['away_id'])]:
                        roster = db.get_roster(uid, league_id)
                        starter_ids = roster.get('starters', {}) if roster else {}
                        score = round(sum(all_points.get(starter_ids.get(sl), {}).get('points', 0.0) for sl in slots), 2)
                        db.fantasy_matchups.update_one(
                            {"id": m['id']},
                            {"$set": {f"{side}_score": score}}
                        )

        flash("Game statistics updated successfully!", "success")
        
        if request.form.get('continue') == 'true':
            return redirect(url_for('admin_game_edit', game_id=game_id))
            
        return redirect(url_for('admin_data'))

    # Fetch rosters for the 'Add Player' dropdowns
    home_team_id = game['summary']['home']['id']
    away_team_id = game['summary']['away']['id']
    
    # Get team names from nfl_teams
    home_team_data = db.db.nfl_teams.find_one({"id": home_team_id})
    away_team_data = db.db.nfl_teams.find_one({"id": away_team_id})
    
    home_team_name = f"{home_team_data['market']} {home_team_data['name']}" if home_team_data else ""
    away_team_name = f"{away_team_data['market']} {away_team_data['name']}" if away_team_data else ""
    
    home_roster = list(db.players.find({"team": home_team_name}).sort("name", 1))
    away_roster = list(db.players.find({"team": away_team_name}).sort("name", 1))

    return render_template('admin_game_edit.html', 
                           game=game, 
                           home_roster=home_roster, 
                           away_roster=away_roster, 
                           active_tab='data')

@app.route('/admin/data/game/<game_id>/add_player', methods=['POST'])
def add_player_to_game(game_id):
    if not session.get('is_site_admin'):
        return {"success": False, "message": "Unauthorized"}, 403
        
    game = db.db.nfl_games.find_one({"id": game_id})
    if not game:
        return {"success": False, "message": "Game not found"}, 404
        
    player_id = request.form.get('player_id')
    side = request.form.get('side') # 'home' or 'away'
    category = request.form.get('category') # 'passing', 'rushing', 'receiving'
    
    player = db.get_player_by_id(player_id)
    if not player:
        return {"success": False, "message": "Player not found"}, 404
        
    # Prepare the stat object
    new_player_stats = {
        "id": player['id'],
        "name": player['name'],
        "jersey": player.get('jersey', ''),
        "position": player.get('position', ''),
        "sr_id": player.get('sr_id', '')
    }
    
    # Initialize category-specific fields
    if category == 'passing':
        new_player_stats.update({"attempts": 0, "completions": 0, "yards": 0, "touchdowns": 0, "interceptions": 0})
    elif category == 'rushing':
        new_player_stats.update({"attempts": 0, "yards": 0, "touchdowns": 0})
    elif category == 'receiving':
        new_player_stats.update({"receptions": 0, "yards": 0, "touchdowns": 0})
    
    new_player_stats["fumbles_lost"] = 0

    # Check if already exists
    current_players = game.get('statistics', {}).get(side, {}).get(category, {}).get('players', [])
    if any(p['id'] == player_id for p in current_players):
        return {"success": False, "message": "Player already in this category"}, 400
        
    # Update DB
    db.db.nfl_games.update_one(
        {"id": game_id},
        {"$push": {f"statistics.{side}.{category}.players": new_player_stats}}
    )
    
    return {"success": True}

@app.route('/admin/finalize_week', methods=['POST'])
def finalize_week():
    if not session.get('is_site_admin'):
        flash("Unauthorized.", "error")
        return redirect(url_for('index'))
    
    # 1. Determine Current Season/Week from settings
    site_settings = db.get_site_settings()
    season = site_settings.get('current_season', 2026)
    week = int(request.form.get('week', 1))
    
    # 2. Fetch all leagues
    all_leagues = list(db.leagues.find())
    
    # 3. Aggregate all team scores for this specific week across all leagues
    all_team_performances = [] # List of {user_id, league_id, score}
    league_winners = [] # List of {league_id, user_id, score}
    
    for league in all_leagues:
        league_id = league['id']
        all_points = get_all_player_data(league_id)
        slots = get_league_roster_slots(league)
        
        league_best_score = -1.0
        league_winner = None

        for u_id in league.get('user_ids', []):
            roster = db.get_roster(u_id, league_id)
            if not roster: continue
            
            starter_ids = roster.get('starters', {})
            score = 0.0
            for slot in slots:
                p_id = starter_ids.get(slot)
                if p_id:
                    score += all_points.get(p_id, {}).get('points', 0.0)
            
            score = round(score, 2)
            perf = {
                "user_id": u_id,
                "league_id": league_id,
                "score": score
            }
            all_team_performances.append(perf)
            
            if score > league_best_score:
                league_best_score = score
                league_winner = u_id

            # Award scoring achievements based on weekly score
            if score >= 100:
                db.award_achievement(u_id, "high_scorer")
            if score >= 150:
                db.award_achievement(u_id, "sharp_shooter")
            if score >= 200:
                db.award_achievement(u_id, "unstoppable")

        if league_winner:
            league_winners.append({
                "league_id": league_id,
                "user_id": league_winner,
                "score": league_best_score
            })

    # 4. Determine Site-Wide MVP (Weekly High Scorer)
    mvp_data = None
    if all_team_performances:
        mvp_performance = max(all_team_performances, key=lambda x: x['score'])
        db.award_achievement(mvp_performance['user_id'], "weekly_mvp")
        
        from bson import ObjectId
        mvp_user = db.users.find_one({"_id": ObjectId(mvp_performance['user_id'])})
        mvp_data = {
            "user_id": mvp_performance['user_id'],
            "username": mvp_user['username'] if mvp_user else "Unknown",
            "score": mvp_performance['score'],
            "league_id": mvp_performance['league_id']
        }

    # 5. Save Permanent Snapshot
    from datetime import datetime
    snapshot = {
        "week_id": f"{season}_W{week}",
        "season": season,
        "week": week,
        "finalized_at": datetime.utcnow(),
        "mvp": mvp_data,
        "league_winners": league_winners,
        "all_performances": all_team_performances # Store all for future history/standings
    }
    db.save_weekly_snapshot(snapshot)

    # --- Per-league matchup achievements ---
    regular_season_weeks = 14
    for league in all_leagues:
        league_id = league['id']
        season_year = league.get('current_season', 2026)
        slots = get_league_roster_slots(league)
        all_points = get_all_player_data(league_id)

        def get_score(u_id):
            roster = db.get_roster(u_id, league_id)
            if not roster: return 0.0
            starter_ids = roster.get('starters', {})
            return round(sum(all_points.get(starter_ids.get(s), {}).get('points', 0.0) for s in slots), 2)

        matchups_this_week = db.get_league_matchups(league_id, week, season_year)

        for m in matchups_this_week:
            h_id, a_id = m['home_id'], m['away_id']
            h_score = get_score(h_id)
            a_score = get_score(a_id)
            margin = abs(h_score - a_score)
            winner_id = h_id if h_score > a_score else (a_id if a_score > h_score else None)
            loser_id  = a_id if h_score > a_score else (h_id if a_score > h_score else None)

            if winner_id:
                # Dominant Victory
                if margin >= 50:
                    db.award_achievement(winner_id, 'dominant_victory')
                # Nail Biter
                if margin < 5:
                    db.award_achievement(winner_id, 'nail_biter')
                # Shutout
                if loser_id and min(h_score, a_score) < 50:
                    db.award_achievement(winner_id, 'shutout')

        # Per-user weekly roster achievements
        for u_id in league.get('user_ids', []):
            roster = db.get_roster(u_id, league_id)
            if not roster: continue
            starter_ids = roster.get('starters', {})
            player_ids_on_roster = roster.get('player_ids', [])

            # Get points for each starter and bench player
            starter_pts = {slot: all_points.get(pid, {}).get('points', 0.0)
                           for slot, pid in starter_ids.items() if pid}
            bench_ids = [pid for pid in player_ids_on_roster if pid not in starter_ids.values()]
            bench_pts = [all_points.get(pid, {}).get('points', 0.0) for pid in bench_ids]

            if starter_pts:
                min_starter = min(starter_pts.values())
                max_bench = max(bench_pts) if bench_pts else 0.0

                # Perfect Lineup — every starter scores 10+
                if min_starter >= 10:
                    db.award_achievement(u_id, 'perfect_lineup')

                # Bench Warmer — a bench player outscores all starters
                if bench_pts and max_bench > max(starter_pts.values()):
                    db.award_achievement(u_id, 'bench_warmer')

            # QB Whisperer — any QB on roster scores 40+
            for pid in player_ids_on_roster:
                player = db.get_player_by_id(pid)
                if player and player.get('position') == 'QB':
                    if all_points.get(pid, {}).get('points', 0.0) >= 40:
                        db.award_achievement(u_id, 'qb_whisperer')
                        break

            # Backfield Boss — 2 RBs score 20+ in same week
            rb_scores = [
                all_points.get(pid, {}).get('points', 0.0)
                for pid in player_ids_on_roster
                if db.get_player_by_id(pid) and db.get_player_by_id(pid).get('position') in ('RB', 'FB')
            ]
            if sum(1 for s in rb_scores if s >= 20) >= 2:
                db.award_achievement(u_id, 'backfield_boss')

            # Receiving Corps — 3 WRs score 15+ in same week
            wr_scores = [
                all_points.get(pid, {}).get('points', 0.0)
                for pid in player_ids_on_roster
                if db.get_player_by_id(pid) and db.get_player_by_id(pid).get('position') == 'WR'
            ]
            if sum(1 for s in wr_scores if s >= 15) >= 3:
                db.award_achievement(u_id, 'receiving_corps')

            # Instant Upgrade — player added this week scores 20+
            # (approximated: any player on roster not in previous week's frozen roster)
            frozen = db.get_frozen_roster(u_id, max(1, week - 1))
            prev_ids = set(frozen.get('player_ids', [])) if frozen else set()
            new_ids = set(player_ids_on_roster) - prev_ids
            for pid in new_ids:
                if all_points.get(pid, {}).get('points', 0.0) >= 20:
                    db.award_achievement(u_id, 'instant_upgrade')
                    break

            # Elite Squad — 3+ players on roster each with 100+ season points
            elite_count = sum(
                1 for pid in player_ids_on_roster
                if all_points.get(pid, {}).get('points', 0.0) >= 100
            )
            if elite_count >= 3:
                db.award_achievement(u_id, 'elite_squad')
            else:
                db.award_achievement(u_id, 'elite_squad', progress=int(elite_count / 3 * 100))

            # Rotation Master — different player in same slot 3 weeks in a row
            # Check QB slot as proxy (most commonly rotated)
            if week >= 3:
                qb_history = set()
                for wk in range(week - 2, week + 1):
                    snap = db.get_weekly_snapshot(season, wk)
                    if snap:
                        for perf in snap.get('all_performances', []):
                            if perf.get('user_id') == u_id and perf.get('league_id') == league_id:
                                # We don\'t store per-slot in snapshot yet, use current as proxy
                                qb_slot_pid = starter_ids.get('QB')
                                if qb_slot_pid:
                                    qb_history.add(qb_slot_pid)
                if len(qb_history) >= 3:
                    db.award_achievement(u_id, 'rotation_master')

        # Buy Low — check if any player acquired via trade last week scores 20+ this week
        for u_id in league.get('user_ids', []):
            if week > 1:
                prev_week_trades = list(db.trades.find({
                    "league_id": league_id,
                    "status": "Finalized",
                    "$or": [
                        {"team_responding.team_id": u_id},
                        {"team_offering.team_id": u_id}
                    ]
                }))
                roster = db.get_roster(u_id, league_id)
                current_player_ids = set(roster.get('player_ids', [])) if roster else set()
                for t in prev_week_trades:
                    received = t['team_offering'].get('player_ids', []) if t['team_responding']['team_id'] == u_id else t['team_responding'].get('player_ids', [])
                    for p_id in received:
                        if p_id in current_player_ids and all_points.get(p_id, {}).get('points', 0.0) >= 20:
                            db.award_achievement(u_id, 'buy_low')
                            break

        # Win streak achievements — look at last N weeks
        all_matchups = db.get_all_league_matchups(league_id, season_year)
        matchups_by_week = {}
        for m in all_matchups:
            matchups_by_week.setdefault(m['week_number'], []).append(m)

        for u_id in league.get('user_ids', []):
            # Build win/loss record per week up to current week
            results = []  # list of (week, won, score, opp_score)
            for wk in range(1, week + 1):
                wk_matchups = matchups_by_week.get(wk, [])
                for m in wk_matchups:
                    if m['home_id'] == u_id or m['away_id'] == u_id:
                        my_score = get_score(u_id)
                        opp_id = m['away_id'] if m['home_id'] == u_id else m['home_id']
                        opp_score = get_score(opp_id)
                        results.append((wk, my_score > opp_score, my_score, opp_score))
                        break

            if not results:
                continue

            # Win streak
            streak = 0
            for _, won, _, _ in reversed(results):
                if won: streak += 1
                else: break

            if streak >= 3:
                db.award_achievement(u_id, 'hot_streak')
            if streak >= 5:
                db.award_achievement(u_id, 'unstoppable_force')

            # Perfect Month (4 consecutive wins)
            for i in range(len(results) - 3):
                if all(results[i+j][1] for j in range(4)):
                    db.award_achievement(u_id, 'perfect_month')
                    break

            # End-of-regular-season achievements
            if week == regular_season_weeks:
                wins = sum(1 for _, won, _, _ in results if won)
                total = len(results)

                # Precision: exactly 7-7
                if wins == 7 and total == 14:
                    db.award_achievement(u_id, 'precision')

                # Ironman: had a full lineup every week (check starters all filled)
                league_slots = get_league_roster_slots(league)
                all_full = True
                for wk in range(1, regular_season_weeks + 1):
                    roster = db.get_roster(u_id, league_id)
                    starters = roster.get('starters', {}) if roster else {}
                    if not all(starters.get(s) for s in league_slots):
                        all_full = False
                        break
                if all_full:
                    db.award_achievement(u_id, 'ironman')

        # End-of-regular-season standings achievements
        if week == regular_season_weeks:
            # Build standings
            standings = []
            for u_id in league.get('user_ids', []):
                wins = 0
                pf = 0.0
                all_matchups_user = db.get_all_league_matchups(league_id, season_year)
                for m in all_matchups_user:
                    if m['home_id'] == u_id or m['away_id'] == u_id:
                        my_score = get_score(u_id)
                        opp_id = m['away_id'] if m['home_id'] == u_id else m['home_id']
                        opp_score = get_score(opp_id)
                        if my_score > opp_score: wins += 1
                        pf += my_score
                standings.append({'user_id': u_id, 'wins': wins, 'pf': pf})

            standings.sort(key=lambda x: (x['wins'], x['pf']), reverse=True)
            total_teams = len(standings)

            for rank, s in enumerate(standings, 1):
                u_id = s['user_id']
                if rank == 1:
                    db.award_achievement(u_id, 'regular_season_champ')
                if rank <= 3:
                    db.award_achievement(u_id, 'podium_finish')

                # Comeback Kid: last place after week 4, top half at end
                if week >= 4:
                    early_wins = 0
                    early_standings = []
                    for uid2 in league.get('user_ids', []):
                        w = sum(1 for m in db.get_all_league_matchups(league_id, season_year)
                                if (m['home_id'] == uid2 or m['away_id'] == uid2)
                                and m['week_number'] <= 4
                                and get_score(uid2) > get_score(m['away_id'] if m['home_id'] == uid2 else m['home_id']))
                        early_standings.append((uid2, w))
                    early_standings.sort(key=lambda x: x[1])
                    last_place_ids = {early_standings[0][0]} if early_standings else set()
                    if u_id in last_place_ids and rank <= total_teams // 2:
                        db.award_achievement(u_id, 'comeback_kid')

            # Mutual Benefit — both teams in a finalized trade finish with winning record
            winning_user_ids = {s['user_id'] for s in standings if s['wins'] > len(results) // 2}
            finalized_trades = list(db.trades.find({"league_id": league_id, "status": "Finalized"}))
            for t in finalized_trades:
                o_id = t['team_offering']['team_id']
                r_id = t['team_responding']['team_id']
                if o_id in winning_user_ids and r_id in winning_user_ids:
                    db.award_achievement(o_id, 'mutual_benefit')
                    db.award_achievement(r_id, 'mutual_benefit')

            # Fair Dealer — no rejected or cancelled trades this season
            for u_id in league.get('user_ids', []):
                bad_trades = db.trades.count_documents({
                    "league_id": league_id,
                    "status": {"$in": ["Rejected", "Cancelled"]},
                    "$or": [
                        {"team_offering.team_id": u_id},
                        {"team_responding.team_id": u_id}
                    ]
                })
                if bad_trades == 0:
                    any_trade = db.trades.count_documents({
                        "league_id": league_id,
                        "$or": [
                            {"team_offering.team_id": u_id},
                            {"team_responding.team_id": u_id}
                        ]
                    })
                    if any_trade > 0:
                        db.award_achievement(u_id, 'fair_dealer')

    if mvp_data:
        flash(f"Week {week} finalized! MVP: {mvp_data['username']} with {mvp_data['score']} pts.", "success")
    else:
        flash(f"Week {week} finalized.", "info")
    return redirect(url_for('admin_panel'))

@app.route('/league/<league_id>/draft/initialize', methods=['POST'])
def initialize_league_draft(league_id):
    league, is_admin = get_league_context(league_id)
    if not is_admin:
        flash("Unauthorized.", "error")
        return redirect(url_for('league_home', league_id=league_id))
    
    season = league.get('current_season', 2026)
    db.initialize_draft(league_id, season)
    flash("Draft initialized and order randomized!", "success")
    return redirect(url_for('league_draft', league_id=league_id))

@app.route('/league/<league_id>/generate_schedule', methods=['POST'])
def generate_schedule(league_id):
    league, is_admin = get_league_context(league_id)
    if not is_admin:
        flash("Unauthorized.", "error")
        return redirect(url_for('league_home', league_id=league_id))
    
    season = league.get('current_season', 2026)
    if db.generate_league_schedule(league_id, season):
        flash(f"14-Week schedule generated for {season}!", "success")
    else:
        flash("Failed to generate schedule. Ensure you have at least 2 members.", "error")
        
    return redirect(url_for('league_matchups', league_id=league_id))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    return redirect(url_for('profile_details'))

@app.route('/profile/details', methods=['GET'])
def profile_details():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    user = db.get_user_by_id(user_id)
    return render_template('profile_details.html', user=user, active_tab='details')

@app.route('/profile/edit', methods=['GET', 'POST'])
def profile_edit():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    if request.method == 'POST':
        new_email = request.form.get('email')
        db.update_user(user_id, {"email": new_email})
        flash("Profile updated successfully!", "success")
        return redirect(url_for('profile_details'))
    user = db.get_user_by_id(user_id)
    return render_template('profile_details_edit.html', user=user, active_tab='details')

@app.route('/profile/achievements')
def profile_achievements():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    user_achievements = db.get_user_achievements(user_id)
    definitions = db.get_achievement_definitions()
    def_map = {d['id']: d for d in definitions}
    achievements_list = []
    for ua in user_achievements:
        d = def_map.get(ua['achievement_id'])
        if d:
            achievements_list.append({
                **d,
                "progress": ua.get('progress', 0),
                "earned_at": ua.get('earned_at'),
                "unlocked": ua.get('progress', 0) >= 100
            })
    earned_ids = {ua['achievement_id'] for ua in user_achievements}
    for d in definitions:
        if d['id'] not in earned_ids:
            achievements_list.append({
                **d,
                "progress": 0,
                "earned_at": None,
                "unlocked": False
            })
    achievements_list.sort(key=lambda x: (not x['unlocked'], x['name']))

    # Group by category, Scoring first
    category_order = ['Scoring', 'Competitive', 'Trading', 'Roster', 'Social', 'General']
    grouped = {}
    for a in achievements_list:
        cat = a.get('category', 'General')
        grouped.setdefault(cat, []).append(a)
    for cat in grouped:
        grouped[cat].sort(key=lambda x: (not x['unlocked'], x['name']))
    sections = [(cat, grouped[cat]) for cat in category_order if cat in grouped]
    for cat in grouped:
        if cat not in category_order:
            sections.append((cat, grouped[cat]))

    return render_template('profile_achievements.html', sections=sections, active_tab='achievements')

@app.route('/profile/actions')
def profile_actions():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('profile_actions.html', active_tab='actions')

@app.route('/speak', methods=['GET', 'POST'])
def speak():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = db.get_user_by_id(session['user_id'])
    if not user.get('is_god'):
        flash("Only a God can speak to the masses.", "error")
        return redirect(url_for('profile_details'))
    if request.method == 'POST':
        message = request.form.get('message')
        if message:
            result = db.create_announcement(announcement_type="GodSpeak", message=message, user_id=str(user['_id']))
            announcement_id = db.announcements.find_one({"_id": result.inserted_id})['id']
            db.users.update_many({}, {"$push": {"announcements": {
                "announcement_id": announcement_id,
                "heard": False,
                "heard_at": None
            }}})
            flash("The masses have heard your word.", "success")
            return redirect(url_for('profile_details'))
    return render_template('speak.html', active_tab='details')

@app.route('/leagues')
def leagues():
    return redirect(url_for('leagues_my'))

@app.route('/league/<league_id>/invite', methods=['POST'])
def league_invite(league_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    league, is_admin = get_league_context(league_id)
    if not league or not is_admin:
        flash("Unauthorized or league not found.", "error")
        return redirect(url_for('leagues'))
    email = request.form.get('email')
    if not email:
        flash("Email address is required.", "error")
        return redirect(url_for('league_invites', league_id=league_id))
    token = db.create_invitation(league_id, email, session['user_id'])
    invite_url = url_for('join_by_token', token=token, _external=True)
    print(f"\n[MOCK EMAIL SERVICE] To: {email}")
    print(f"Subject: You've been invited to join {league['name']}!")
    print(f"Link: {invite_url}\n")
    flash(f"Invitation sent to {email}!", "success")
    return redirect(url_for('league_invites', league_id=league_id))

@app.route('/league/<league_id>/invites')
def league_invites(league_id):
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))
    pending_invites = db.get_league_invitations(league_id) if is_admin else []
    return render_template('league_invites.html', league=league, is_admin=is_admin, pending_invites=pending_invites)

@app.route('/league/<league_id>/waivers')
def league_waivers(league_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))

    user_id = session['user_id']
    current_week = league.get('current_week', 1)

    # Build ownership map
    all_rosters = list(db.rosters.find({"league_id": league_id}))
    from bson import ObjectId
    users_data = {str(u['_id']): u for u in db.users.find({"_id": {"$in": [ObjectId(r['user_id']) for r in all_rosters]}})}
    player_ownership = {}
    for roster in all_rosters:
        owner = users_data.get(roster['user_id'])
        owner_name = (roster.get('team', {}).get('name') if roster.get('team') else None) or (owner['username'] if owner else 'Unknown')
        for p_id in roster.get('player_ids', []):
            player_ownership[p_id] = {'owner_id': roster['user_id'], 'owner_name': owner_name}

    # My roster for drop candidates
    my_roster = db.get_roster(user_id, league_id)
    my_player_ids = my_roster.get('player_ids', []) if my_roster else []
    my_players = []
    for p_id in my_player_ids:
        p = db.get_player_by_id(p_id)
        if p:
            my_players.append({'id': p_id, 'name': p.get('name', 'Unknown'), 'position': p.get('position', '?')})

    # My pending claims this week
    my_claims = db.get_user_waiver_claims(league_id, user_id, current_week)
    claimed_player_ids = {c['player_id'] for c in my_claims if c['status'] == 'Pending'}

    # Decorate claims with player/drop names
    player_cache = {}
    def _pname(pid):
        if pid and pid not in player_cache:
            p = db.get_player_by_id(pid)
            player_cache[pid] = p.get('name', 'Unknown') if p else 'Unknown'
        return player_cache.get(pid, '—')

    for c in my_claims:
        c['player_name'] = _pname(c['player_id'])
        c['drop_name'] = _pname(c['drop_player_id']) if c['drop_player_id'] else '—'

    # Waiver priority list
    priority = db.get_waiver_priority(league_id)
    priority_display = []
    for i, uid in enumerate(priority):
        u = db.get_user_by_id(uid)
        r = db.get_roster(uid, league_id)
        team_name = (r.get('team', {}).get('name') if r else None) or (u['username'] if u else 'Unknown')
        priority_display.append({'rank': i + 1, 'team_name': team_name, 'is_me': uid == user_id})

    # Recent processed claims (last 20)
    all_claims = db.get_waiver_claims(league_id)
    processed = sorted(
        [c for c in all_claims if c['status'] in ('Awarded', 'Failed', 'Cancelled')],
        key=lambda c: c.get('processed_at') or c['created_at'], reverse=True
    )[:20]
    for c in processed:
        c['player_name'] = _pname(c['player_id'])
        c['drop_name'] = _pname(c['drop_player_id']) if c['drop_player_id'] else '—'
        u = db.get_user_by_id(c['user_id'])
        r = db.get_roster(c['user_id'], league_id)
        c['team_name'] = (r.get('team', {}).get('name') if r else None) or (u['username'] if u else 'Unknown')

    all_season_data = get_all_player_data(league_id)

    # Build free agent list
    owned_ids = set(player_ownership.keys())
    free_agents = []
    for p in db.get_all_players():
        if p['id'] not in owned_ids:
            pd = all_season_data.get(p['id'], {})
            free_agents.append({
                'id': p['id'],
                'name': p.get('name', 'Unknown'),
                'position': p.get('position', '?'),
                'team': p.get('team', '?'),
                'points': round(pd.get('points', 0.0), 2),
                'already_claimed': p['id'] in claimed_player_ids,
            })
    free_agents.sort(key=lambda x: x['points'], reverse=True)

    return render_template('league_waivers.html',
        league=league, is_admin=is_admin,
        current_week=current_week,
        my_players=my_players,
        my_claims=my_claims,
        claimed_player_ids=list(claimed_player_ids),
        priority_display=priority_display,
        processed_claims=processed,
        player_ownership=player_ownership,
        free_agents=free_agents,
    )


@app.route('/league/<league_id>/waivers/claim', methods=['POST'])
def waiver_claim(league_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))

    user_id = session['user_id']
    player_id = request.form.get('player_id', '').strip()
    drop_player_id = request.form.get('drop_player_id', '').strip() or None
    current_week = league.get('current_week', 1)

    if not player_id:
        flash("No player selected.", "error")
        return redirect(url_for('league_waivers', league_id=league_id))

    # Check player isn't already owned
    all_rosters = list(db.rosters.find({"league_id": league_id}))
    owned = {p_id for r in all_rosters for p_id in r.get('player_ids', [])}
    if player_id in owned:
        flash("That player is already on a roster.", "error")
        return redirect(url_for('league_waivers', league_id=league_id))

    # Check no duplicate pending claim for same player
    existing = db.get_user_waiver_claims(league_id, user_id, current_week)
    if any(c['player_id'] == player_id and c['status'] == 'Pending' for c in existing):
        flash("You already have a pending claim for that player.", "error")
        return redirect(url_for('league_waivers', league_id=league_id))

    priority_list = db.get_waiver_priority(league_id)
    priority = priority_list.index(user_id) if user_id in priority_list else 999

    db.submit_waiver_claim(league_id, user_id, player_id, drop_player_id, current_week, priority)
    flash("Waiver claim submitted.", "success")
    return redirect(url_for('league_waivers', league_id=league_id))


@app.route('/league/<league_id>/waivers/cancel/<claim_id>', methods=['POST'])
def waiver_cancel(league_id, claim_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db.cancel_waiver_claim(claim_id, session['user_id'])
    flash("Claim cancelled.", "info")
    return redirect(url_for('league_waivers', league_id=league_id))


@app.route('/league/<league_id>/waivers/process', methods=['POST'])
def waiver_process(league_id):
    """Admin-triggered waiver processing."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    league, is_admin = get_league_context(league_id)
    if not league or not is_admin:
        flash("Unauthorized.", "error")
        return redirect(url_for('leagues'))

    current_week = league.get('current_week', 1)
    pending = db.get_waiver_claims(league_id, status='Pending', week_number=current_week)
    # Sort by priority then created_at
    pending.sort(key=lambda c: (c['priority'], c['created_at']))

    awarded_players = set()  # player_ids already awarded this run
    max_roster = league.get('rules', {}).get('roster', {}).get('max_roster_size', 15)
    awarded = 0
    failed = 0

    for claim in pending:
        user_id = claim['user_id']
        player_id = claim['player_id']
        drop_id = claim['drop_player_id']

        # Skip if player already awarded to someone else
        if player_id in awarded_players:
            db.update_waiver_claim_status(claim['id'], 'Failed', 'Player already awarded to another team')
            failed += 1
            continue

        # Check player still free
        all_rosters = list(db.rosters.find({"league_id": league_id}))
        owned = {p_id for r in all_rosters for p_id in r.get('player_ids', [])}
        if player_id in owned:
            db.update_waiver_claim_status(claim['id'], 'Failed', 'Player no longer available')
            failed += 1
            continue

        # Check roster space (after drop)
        my_roster = db.get_roster(user_id, league_id)
        my_ids = list(my_roster.get('player_ids', [])) if my_roster else []
        if drop_id and drop_id in my_ids:
            my_ids.remove(drop_id)
        if len(my_ids) >= max_roster:
            db.update_waiver_claim_status(claim['id'], 'Failed', 'Roster full — no drop player specified or drop invalid')
            failed += 1
            continue

        # Execute: drop then add
        if drop_id:
            final_ids = [p for p in (my_roster.get('player_ids', []) if my_roster else []) if p != drop_id]
        else:
            final_ids = list(my_roster.get('player_ids', [])) if my_roster else []
        final_ids.append(player_id)
        db.update_roster(user_id, league_id, final_ids)

        db.update_waiver_claim_status(claim['id'], 'Awarded')
        awarded_players.add(player_id)
        db.rotate_waiver_priority(league_id, user_id)

        # Cancel other pending claims for the same player
        for other in pending:
            if other['player_id'] == player_id and other['id'] != claim['id'] and other['status'] == 'Pending':
                db.update_waiver_claim_status(other['id'], 'Failed', 'Player awarded to higher priority team')

        awarded += 1

    flash(f"Waivers processed: {awarded} awarded, {failed} failed.", "success")
    return redirect(url_for('league_waivers', league_id=league_id))


@app.route('/league/<league_id>/waivers/search')
def waiver_search(league_id):
    if 'user_id' not in session:
        return jsonify([])
    q = request.args.get('q', '').lower()
    if len(q) < 2:
        return jsonify([])
    all_rosters = list(db.rosters.find({"league_id": league_id}))
    owned = {p_id for r in all_rosters for p_id in r.get('player_ids', [])}
    results = [
        {'id': p['id'], 'name': p['name'], 'position': p['position'], 'team': p.get('team', '')}
        for p in db.get_all_players()
        if p['id'] not in owned and (q in p['name'].lower() or q in p.get('team', '').lower() or q in p['position'].lower())
    ][:20]
    return jsonify(results)


@app.route('/league/<league_id>/archives')
def league_archives(league_id):
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))

    # Fetch all archives for this league, sorted by season desc
    archives = list(db.db.league_archives.find({"league_id": league_id}).sort("season", -1))

    # Resolve user_id -> team_name for schedule display
    user_cache = {}
    def _team(uid, roster_list):
        if uid in user_cache:
            return user_cache[uid]
        for r in roster_list:
            if r['user_id'] == uid:
                user_cache[uid] = r['team_name']
                return r['team_name']
        user_cache[uid] = uid
        return uid

    for a in archives:
        rosters = a.get('final_rosters', [])
        # Resolve player IDs in waiver claims to names
        p_cache = {}
        def _pname(pid):
            if not pid: return None
            if pid not in p_cache:
                p = db.get_player_by_id(pid)
                p_cache[pid] = p.get('name', pid) if p else pid
            return p_cache[pid]
        for c in a.get('waiver_claims', []):
            c['player_name'] = _pname(c.get('player_id'))
            c['drop_name'] = _pname(c.get('drop_player_id'))
        for m in a.get('schedule', []):
            m['home_name'] = _team(m['home_id'], rosters)
            m['away_name'] = _team(m['away_id'], rosters)
        user_cache.clear()

    selected_season = request.args.get('season', archives[0]['season'] if archives else None)
    if selected_season:
        selected_season = int(selected_season)
    archive = next((a for a in archives if a['season'] == selected_season), None)

    return render_template('league_archives.html', league=league, is_admin=is_admin,
                           archives=archives, archive=archive, selected_season=selected_season)


@app.route('/league/<league_id>/transactions')
def league_transactions(league_id):
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))

    all_trades = db.get_league_trades(league_id)
    completed_trades = [t for t in all_trades if t['status'] == 'Finalized']
    completed_trades.sort(key=lambda t: t.get('status_modified') or t['_id'].generation_time, reverse=True)

    # Resolve player names and team names
    user_cache = {}
    player_cache = {}
    roster_cache = {}

    def get_team_name(user_id):
        if user_id not in user_cache:
            u = db.get_user_by_id(user_id)
            r = db.get_roster(user_id, league_id)
            roster_cache[user_id] = r
            user_cache[user_id] = {
                'username': u['username'] if u else 'Unknown',
                'team_name': (r.get('team', {}).get('name') if r else None) or (u['username'] if u else 'Unknown')
            }
        return user_cache[user_id]['team_name']

    def get_player_name(player_id):
        if player_id not in player_cache:
            p = db.get_player_by_id(player_id)
            player_cache[player_id] = p.get('name', 'Unknown') if p else 'Unknown'
        return player_cache[player_id]

    decorated = []
    for t in completed_trades:
        o_id = t['team_offering']['team_id']
        r_id = t['team_responding']['team_id']
        decorated.append({
            'id': t['id'],
            'date': t.get('status_modified') or t['_id'].generation_time,
            'offering_team': get_team_name(o_id),
            'responding_team': get_team_name(r_id),
            'offering_players': [get_player_name(p) for p in t['team_offering'].get('player_ids', [])],
            'responding_players': [get_player_name(p) for p in t['team_responding'].get('player_ids', [])],
            'offering_picks': t['team_offering'].get('draft_picks', []),
            'responding_picks': t['team_responding'].get('draft_picks', []),
        })

    # Awarded waiver claims
    all_claims = db.get_waiver_claims(league_id)
    awarded_claims = sorted(
        [c for c in all_claims if c['status'] == 'Awarded'],
        key=lambda c: c.get('processed_at') or c['created_at'], reverse=True
    )
    decorated_waivers = []
    for c in awarded_claims:
        u = db.get_user_by_id(c['user_id'])
        r = db.get_roster(c['user_id'], league_id)
        team_name = (r.get('team', {}).get('name') if r else None) or (u['username'] if u else 'Unknown')
        decorated_waivers.append({
            'date': c.get('processed_at') or c['created_at'],
            'week': c.get('week_number', '—'),
            'team_name': team_name,
            'player_added': get_player_name(c['player_id']),
            'player_dropped': get_player_name(c['drop_player_id']) if c.get('drop_player_id') else None,
        })

    # Drops
    all_drops = db.get_league_drops(league_id)
    decorated_drops = []
    for d in all_drops:
        u = db.get_user_by_id(d['user_id'])
        r = db.get_roster(d['user_id'], league_id)
        team_name = (r.get('team', {}).get('name') if r else None) or (u['username'] if u else 'Unknown')
        decorated_drops.append({
            'date': d['dropped_at'],
            'team_name': team_name,
            'player_name': get_player_name(d['player_id']),
        })

    # IR Moves
    all_ir = db.get_league_ir_moves(league_id)
    decorated_ir = []
    for m in all_ir:
        u = db.get_user_by_id(m['user_id'])
        r = db.get_roster(m['user_id'], league_id)
        team_name = (r.get('team', {}).get('name') if r else None) or (u['username'] if u else 'Unknown')
        decorated_ir.append({
            'date': m['moved_at'],
            'team_name': team_name,
            'player_name': get_player_name(m['player_id']),
            'ir_slot': m['ir_slot'],
            'direction': m['direction'],
        })

    active_tab = request.args.get('tab', 'trades')
    return render_template('league_transactions.html', league=league, is_admin=is_admin,
                           completed_trades=decorated, awarded_waivers=decorated_waivers,
                           drops=decorated_drops, ir_moves=decorated_ir, active_tab=active_tab)

@app.route('/league/<league_id>/watchlist')
def league_watchlist(league_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))
    user_id = session['user_id']
    watchlist_ids = db.get_watchlist(user_id, league_id)

    # Build ownership map
    all_rosters = list(db.rosters.find({"league_id": league_id}))
    from bson import ObjectId
    users_data = {str(u['_id']): u for u in db.users.find({"_id": {"$in": [ObjectId(r['user_id']) for r in all_rosters]}})}
    player_ownership = {}
    for roster in all_rosters:
        owner = users_data.get(roster['user_id'])
        owner_name = (roster.get('team', {}).get('name') if roster.get('team') else None) or (owner['username'] if owner else 'Unknown')
        for p_id in roster.get('player_ids', []):
            player_ownership[p_id] = {'owner_id': roster['user_id'], 'owner_name': owner_name}

    all_season_data = get_all_player_data(league_id)
    my_roster = db.get_roster(user_id, league_id)
    my_player_ids = set(my_roster.get('player_ids', [])) if my_roster else set()

    watchlist_players = []
    for p_id in watchlist_ids:
        p = db.get_player_by_id(p_id)
        if not p:
            continue
        pd = all_season_data.get(p_id, {})
        ownership = player_ownership.get(p_id)
        watchlist_players.append({
            'id': p_id,
            'name': p.get('name', 'Unknown'),
            'position': p.get('position', '?'),
            'team': p.get('team', '?'),
            'points': round(pd.get('points', 0.0), 2),
            'owned_by': ownership['owner_name'] if ownership else None,
            'owner_id': ownership['owner_id'] if ownership else None,
            'is_mine': p_id in my_player_ids,
            'in_league': bool(ownership),
        })
    watchlist_players.sort(key=lambda x: x['points'], reverse=True)

    return render_template('league_watchlist.html', league=league, is_admin=is_admin,
                           watchlist_players=watchlist_players, watchlist_ids=watchlist_ids)

@app.route('/league/<league_id>/watchlist/add/<player_id>', methods=['POST'])
def watchlist_add(league_id, player_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db.add_to_watchlist(session['user_id'], league_id, player_id)
    return redirect(request.referrer or url_for('league_watchlist', league_id=league_id))

@app.route('/league/<league_id>/watchlist/remove/<player_id>', methods=['POST'])
def watchlist_remove(league_id, player_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db.remove_from_watchlist(session['user_id'], league_id, player_id)
    return redirect(request.referrer or url_for('league_watchlist', league_id=league_id))

@app.route('/league/<league_id>/watchlist/search')
def watchlist_search(league_id):
    if 'user_id' not in session:
        return jsonify([])
    q = request.args.get('q', '').lower()
    if len(q) < 2:
        return jsonify([])
    all_players = db.get_all_players()
    results = [
        {'id': p['id'], 'name': p['name'], 'position': p['position'], 'team': p.get('team', '')}
        for p in all_players
        if q in p['name'].lower() or q in p.get('team', '').lower() or q in p['position'].lower()
    ][:20]
    return jsonify(results)

@app.route('/join/<token>')
def join_by_token(token):
    invitation = db.get_invitation_by_token(token)
    if not invitation:
        flash("Invitation link is invalid or has expired.", "error")
        return redirect(url_for('index'))
    league = db.get_league(invitation['league_id'])
    if not league:
        flash("League no longer exists.", "error")
        return redirect(url_for('index'))
    if 'user_id' in session:
        user_id = session['user_id']
        if user_id in league.get('user_ids', []):
            flash("You are already a member of this league.", "info")
        else:
            db.add_user_to_league(league['id'], user_id)
            for year in [2026, 2027, 2028]:
                for rd in range(1, 6):
                    db.add_draft_pick_to_roster(user_id, league['id'], user_id, year, rd, 0)
            db.update_invitation_status(invitation['id'], "accepted")
            flash(f"Welcome! You've successfully joined {league['name']}.", "success")
        return redirect(url_for('league_home', league_id=league['id']))
    session['pending_invite_token'] = token
    return render_template('index.html', invite_league=league)

@app.route('/leagues/create', methods=['GET', 'POST'])
def create_league():
    if 'user_id' not in session:
        flash("You must be logged in to create a league.", "error")
        return redirect(url_for('login'))
    if request.method == 'POST':
        league_id = str(uuid.uuid4())
        league_name = request.form.get('league_name')
        league_type = request.form.get('league_type')
        scoring_format = request.form.get('scoring_format')
        positional_format = request.form.get('positional_format')
        play_format = request.form.get('play_format')
        max_teams = request.form.get('max_teams', 12)
        has_divisions = request.form.get('has_divisions') == 'on'
        num_divisions = request.form.get('num_divisions') if has_divisions else None
        user_id = session['user_id']
        db.create_league(league_id, league_name, league_type, scoring_format, positional_format, play_format, max_teams, has_divisions, num_divisions, [user_id], [user_id])
        for year in [2026, 2027, 2028]:
            for rd in range(1, 6):
                db.add_draft_pick_to_roster(user_id, league_id, user_id, year, rd, 0)
        flash(f"League '{league_name}' created successfully!", "success")
        return redirect(url_for('leagues_my'))
    selected_type = request.args.get('type')
    return render_template('league_create.html', active_tab='create', selected_type=selected_type)

@app.route('/leagues/my')
def leagues_my():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    my_leagues = list(db.leagues.find({"user_ids": user_id}))
    return render_template('leagues_my.html', leagues=my_leagues, active_tab='my')

@app.route('/leagues/public')
def leagues_public():
    all_leagues = list(db.leagues.find())
    return render_template('leagues_public.html', leagues=all_leagues, active_tab='public')

@app.route('/leagues/find')
def leagues_find():
    return render_template('leagues_find.html', active_tab='find')

@app.route('/leagues/types')
def leagues_types():
    types = [
        {"name": "Redraft", "description": "The most common way to play. Start with a fresh roster every season through a snake or auction draft. Perfect for those who love the excitement of building a new team each year."},
        {"name": "Keeper", "description": "Managers can retain a specific number of players from their previous season's roster. This adds a layer of long-term strategy while still keeping the draft fresh and competitive."},
        {"name": "Dynasty", "description": "The ultimate long-term commitment. You keep your entire roster from year to year. Annual drafts consist only of rookies, making scouting and future potential more critical than ever."},
        {"name": "Best Ball", "description": "No weekly lineup management required. The system automatically selects your highest-scoring players at each position each week to give you the best possible score."},
        {"name": "Vampire", "description": "One manager (the Vampire) starts with no draft picks and builds their team from undrafted players. If the Vampire wins, they earn the right to 'steal' a starter from their opponent."},
        {"name": "Guillotine", "description": "Every week, the lowest-scoring team is eliminated. Their entire roster is released into the free-agent pool, creating a chaotic scramble for the remaining managers to bid on superstars."}
    ]
    return render_template('league_types.html', league_types=types, active_tab='types')

@app.route('/join_league/<league_id>', methods=['POST'])
def join_league(league_id):
    if 'user_id' not in session:
        flash("You must be logged in to join a league.", "error")
        return redirect(url_for('login'))
    user_id = session['user_id']
    db.add_user_to_league(league_id, user_id)
    for year in [2026, 2027, 2028]:
        for rd in range(1, 6):
            db.add_draft_pick_to_roster(user_id, league_id, user_id, year, rd, 0)
    flash("Successfully joined the league!", "success")
    return redirect(url_for('leagues'))

@app.route('/league/<league_id>')
def league_home(league_id):
    league = db.get_league(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))
    if 'user_id' in session:
        db.update_user_last_visited(session['user_id'])
    members = []
    is_admin = False
    current_user_id = session.get('user_id')
    league_admins = league.get('administrators', [])
    if current_user_id and current_user_id in league_admins:
        is_admin = True
    for u_id in league.get('user_ids', []):
        from bson import ObjectId
        user = db.users.find_one({"_id": ObjectId(u_id)})
        if user:
            roster = db.get_roster(u_id, league_id)
            roster_count = len(roster.get('player_ids', [])) if roster else 0
            frozen = db.get_frozen_roster(u_id, 1) is not None
            last_visited = user.get('last_visited')
            iso_visited = None
            if last_visited:
                iso_visited = last_visited.isoformat()
                if not iso_visited.endswith('Z') and '+' not in iso_visited:
                    iso_visited += 'Z'
            team_name = "Unnamed Team"
            if roster and roster.get('team') and roster.get('team').get('name'):
                team_name = roster.get('team').get('name')
            members.append({
                "id": str(user['_id']),
                "username": user['username'],
                "team_name": team_name,
                "roster_count": roster_count,
                "frozen": frozen,
                "last_visited": iso_visited,
                "is_league_admin": str(user['_id']) in league_admins
            })
    pending_invites = []
    if is_admin:
        pending_invites = db.get_league_invitations(league_id)

    # Fetch pending trade offers for the logged-in user
    pending_trades = []
    if current_user_id and current_user_id in league.get('user_ids', []):
        all_trades = db.get_league_trades(league_id)
        for trade in all_trades:
            if trade['status'] != 'Pending':
                continue
            is_offering = trade['team_offering']['team_id'] == current_user_id
            is_responding = trade['team_responding']['team_id'] == current_user_id
            if not is_offering and not is_responding:
                continue
            other_id = trade['team_responding']['team_id'] if is_offering else trade['team_offering']['team_id']
            other_user = db.get_user_by_id(other_id)
            other_roster = db.get_roster(other_id, league_id)
            other_name = (other_roster.get('team', {}).get('name') if other_roster else None) or (other_user['username'] if other_user else 'Unknown')
            pending_trades.append({
                'id': trade['id'],
                'direction': 'outgoing' if is_offering else 'incoming',
                'other_name': other_name,
                'player_count': len(trade['team_offering'].get('player_ids', [])) + len(trade['team_responding'].get('player_ids', [])),
                'pick_count': len(trade['team_offering'].get('draft_picks', [])) + len(trade['team_responding'].get('draft_picks', []))
            })

    # Build standings for sidebar
    season = league.get('current_season', 2026)
    all_points_data = get_all_player_data(league_id)
    slots = get_league_roster_slots(league)
    all_matchups = db.get_all_league_matchups(league_id, season)
    standings_map = {}
    for m_obj in members:
        standings_map[m_obj['id']] = {
            'team_name': m_obj['team_name'], 'wins': 0, 'losses': 0, 'ties': 0,
            'points_for': 0.0, 'pct': 0.0
        }
    def _weekly_score(u_id, _week):
        roster = db.get_roster(u_id, league_id)
        if not roster: return 0.0
        starter_ids = roster.get('starters', {})
        return round(sum(all_points_data.get(starter_ids.get(sl), {}).get('points', 0.0) for sl in slots), 2)
    for m in all_matchups:
        if m['status'] == 'scheduled':
            h_id, a_id = m['home_id'], m['away_id']
            h_score = _weekly_score(h_id, m['week_number'])
            a_score = _weekly_score(a_id, m['week_number'])
            for uid, my_score, opp_score in [(h_id, h_score, a_score), (a_id, a_score, h_score)]:
                if uid in standings_map:
                    standings_map[uid]['points_for'] += my_score
                    if my_score > opp_score: standings_map[uid]['wins'] += 1
                    elif opp_score > my_score: standings_map[uid]['losses'] += 1
                    else: standings_map[uid]['ties'] += 1
    for s in standings_map.values():
        total = s['wins'] + s['losses'] + s['ties']
        s['pct'] = (s['wins'] + 0.5 * s['ties']) / total if total > 0 else 0.0
        s['points_for'] = round(s['points_for'], 2)
    standings_list = sorted(standings_map.values(), key=lambda x: (x['pct'], x['points_for']), reverse=True)

    # Build current user's roster for display
    my_roster_players = []
    if current_user_id and current_user_id in league.get('user_ids', []):
        my_roster = db.get_roster(current_user_id, league_id)
        if my_roster:
            starter_ids = set(my_roster.get('starters', {}).values())
            ir_ids = set(my_roster.get('ir', {}).values())
            for p_id in my_roster.get('player_ids', []):
                p = db.get_player_by_id(p_id)
                if p:
                    if p_id in ir_ids:
                        status = 'ir'
                    elif p_id in starter_ids:
                        status = 'starter'
                    else:
                        status = 'bench'
                    my_roster_players.append({
                        'name': p.get('name', 'Unknown'),
                        'position': p.get('position', '?'),
                        'team': p.get('team', '?'),
                        'is_starter': status == 'starter',
                        'status': status,
                    })
            my_roster_players.sort(key=lambda x: ({'starter': 0, 'bench': 1, 'ir': 2}[x['status']], x['position'], x['name']))

    # Build current week matchups for sidebar
    current_week = league.get('current_week', 1)
    week_matchups = db.get_league_matchups(league_id, current_week, season)
    week_points_data = get_all_player_data(league_id, week=current_week)
    for m in week_matchups:
        for side in ['home', 'away']:
            u_id = m[f'{side}_id']
            from bson import ObjectId
            user = db.users.find_one({"_id": ObjectId(u_id)})
            roster = db.get_roster(u_id, league_id)
            m[f'{side}_name'] = (roster.get('team', {}).get('name') if roster else None) or (user['username'] if user else 'Unknown')
            starter_ids = roster.get('starters', {}) if roster else {}
            m[f'{side}_score'] = round(sum(week_points_data.get(starter_ids.get(sl), {}).get('points', 0.0) for sl in slots), 2)

    # Build message board preview
    board_threads = db.get_threads(league_id)
    user_cache = {}
    def _get_username(uid):
        if uid not in user_cache:
            u = db.get_user_by_id(uid)
            user_cache[uid] = u['username'] if u else 'Unknown'
        return user_cache[uid]
    for t in board_threads[:5]:  # limit to 5 most recent threads
        t['author_name'] = _get_username(t['author_id'])
        for p in t.get('posts', []):
            p['author_name'] = _get_username(p['author_id'])

    # Build watchlist for sidebar
    home_watchlist = []
    if current_user_id and current_user_id in league.get('user_ids', []):
        watchlist_ids = db.get_watchlist(current_user_id, league_id)
        all_rosters = list(db.rosters.find({"league_id": league_id}))
        player_ownership = {}
        for r in all_rosters:
            for p_id in r.get('player_ids', []):
                player_ownership[p_id] = r['user_id']
        my_player_ids = set(db.get_roster(current_user_id, league_id).get('player_ids', []) if db.get_roster(current_user_id, league_id) else [])
        for p_id in watchlist_ids:
            p = db.get_player_by_id(p_id)
            if p:
                home_watchlist.append({
                    'id': p_id,
                    'name': p.get('name', 'Unknown'),
                    'position': p.get('position', '?'),
                    'points': round(all_points_data.get(p_id, {}).get('points', 0.0), 2),
                    'is_mine': p_id in my_player_ids,
                    'in_league': p_id in player_ownership,
                })
        home_watchlist.sort(key=lambda x: x['points'], reverse=True)

    # Build recent transactions for home page
    all_trades = db.get_league_trades(league_id)
    recent_trades = sorted(
        [t for t in all_trades if t['status'] == 'Finalized'],
        key=lambda t: t.get('status_modified') or t['_id'].generation_time,
        reverse=True
    )[:5]
    trade_user_cache = {}
    trade_player_cache = {}
    def _trade_team(uid):
        if uid not in trade_user_cache:
            u = db.get_user_by_id(uid)
            r = db.get_roster(uid, league_id)
            trade_user_cache[uid] = (r.get('team', {}).get('name') if r else None) or (u['username'] if u else 'Unknown')
        return trade_user_cache[uid]
    def _trade_player(pid):
        if pid not in trade_player_cache:
            p = db.get_player_by_id(pid)
            trade_player_cache[pid] = p.get('name', 'Unknown') if p else 'Unknown'
        return trade_player_cache[pid]
    decorated_trades = []
    for t in recent_trades:
        decorated_trades.append({
            'date': t.get('status_modified') or t['_id'].generation_time,
            'offering_team': _trade_team(t['team_offering']['team_id']),
            'responding_team': _trade_team(t['team_responding']['team_id']),
            'offering_players': [_trade_player(p) for p in t['team_offering'].get('player_ids', [])],
            'responding_players': [_trade_player(p) for p in t['team_responding'].get('player_ids', [])],
            'offering_picks': t['team_offering'].get('draft_picks', []),
            'responding_picks': t['team_responding'].get('draft_picks', []),
        })

    return render_template('league_home.html', league=league, members=members, is_admin=is_admin, pending_invites=pending_invites, pending_trades=pending_trades, standings=standings_list, my_roster_players=my_roster_players, week_matchups=week_matchups, current_week=current_week, home_watchlist=home_watchlist, board_threads=board_threads, recent_trades=decorated_trades)

@app.route('/league/<league_id>/edit', methods=['GET', 'POST'])
def edit_league(league_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))
    if not is_admin:
        flash("You are not authorized to edit this league.", "error")
        return redirect(url_for('league_home', league_id=league_id))
    if request.method == 'POST':
        has_divisions = request.form.get('has_divisions') == 'on'
        new_num_divisions = int(request.form.get('num_divisions')) if has_divisions else None
        update_data = {
            "name": request.form.get('league_name'),
            "league_type": request.form.get('league_type'),
            "scoring_format": request.form.get('scoring_format'),
            "positional_format": request.form.get('positional_format'),
            "play_format": request.form.get('play_format'),
            "max_teams": int(request.form.get('max_teams', 12)),
            "has_divisions": has_divisions,
            "num_divisions": new_num_divisions,
            "salary_settings": {
                "active_model": request.form.get('active_model', 'none'),
                "salary_cap": int(request.form.get('salary_cap', 100000000)),
                "point_multiplier": int(request.form.get('point_multiplier', 100000)),
                "td_value": int(request.form.get('td_value', 100000)),
                "base_salary": int(request.form.get('base_salary', 500000))
            }
        }
        if has_divisions and new_num_divisions:
            current_names = league.get('division_names', [])
            current_assignments = league.get('division_assignments', {})
            new_assignments = {}
            if len(current_names) < new_num_divisions:
                for i in range(len(current_names), new_num_divisions):
                    current_names.append(f"Division {i+1}")
                for i in range(new_num_divisions):
                    new_assignments[str(i)] = current_assignments.get(str(i), [])
            elif len(current_names) > new_num_divisions:
                current_names = current_names[:new_num_divisions]
                for i in range(new_num_divisions):
                    new_assignments[str(i)] = current_assignments.get(str(i), [])
            else:
                new_assignments = current_assignments
            update_data["division_names"] = current_names
            update_data["division_assignments"] = new_assignments
        else:
            update_data["division_names"] = []
            update_data["division_assignments"] = {}
        db.update_league(league_id, update_data)
        flash("League updated successfully!", "success")
        return redirect(url_for('league_home', league_id=league_id))
    return render_template('league_edit.html', league=league, active_tab='my')

@app.route('/league/<league_id>/scoring', methods=['GET', 'POST'])
def league_scoring(league_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))
    if not is_admin:
        flash("Unauthorized.", "error")
        return redirect(url_for('league_home', league_id=league_id))
    if request.method == 'POST':
        new_settings = {
            "passing": {
                "td": float(request.form.get('pass_td', 6.0)),
                "yard": float(request.form.get('pass_yard', 0.1)),
                "attempt": float(request.form.get('pass_attempt', 0.2)),
                "completion": float(request.form.get('pass_completion', 0.5)),
                "interception": float(request.form.get('pass_int', -2.0))
            },
            "rushing": {
                "td": float(request.form.get('rush_td', 6.0)),
                "yard": float(request.form.get('rush_yard', 0.1)),
                "attempt": float(request.form.get('rush_attempt', 0.2))
            },
            "receiving": {
                "td": float(request.form.get('rec_td', 6.0)),
                "yard": float(request.form.get('rec_yard', 0.1)),
                "reception": float(request.form.get('rec_reception', 1.0))
            },
            "misc": {
                "fumble_lost": float(request.form.get('fumble_lost', -3.0))
            }
        }
        db.update_league(league_id, {"scoring_settings": new_settings})
        flash("Scoring settings updated successfully!", "success")
        return redirect(url_for('league_home', league_id=league_id))
    scoring = league.get('scoring_settings', db.get_league_scoring_settings(league_id))
    return render_template('league_scoring.html', league=league, scoring=scoring, active_tab='my')

@app.route('/league/<league_id>/divisions', methods=['GET', 'POST'])
def league_divisions(league_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))
    if not is_admin:
        flash("Unauthorized.", "error")
        return redirect(url_for('league_home', league_id=league_id))
    if not league.get('has_divisions'):
        flash("Divisions are not enabled for this league.", "error")
        return redirect(url_for('league_home', league_id=league_id))
    if request.method == 'POST':
        names = request.form.getlist('division_names')
        db.update_league(league_id, {"division_names": names})
        flash("Division names updated!", "success")
        return redirect(url_for('league_home', league_id=league_id))
    return render_template('league_divisions.html', league=league, active_tab='my')

@app.route('/league/<league_id>/assign_divisions', methods=['GET', 'POST'])
def league_assign_divisions(league_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))
    if not is_admin:
        flash("Unauthorized.", "error")
        return redirect(url_for('league_home', league_id=league_id))
    if not league.get('has_divisions'):
        flash("Divisions are not enabled for this league.", "error")
        return redirect(url_for('league_home', league_id=league_id))
    if request.method == 'POST':
        new_assignments = {str(i): [] for i in range(league.get('num_divisions', 0))}
        for u_id in league.get('user_ids', []):
            div_index = request.form.get(f'assignment_{u_id}')
            if div_index:
                new_assignments[div_index].append(u_id)
        db.update_league(league_id, {"division_assignments": new_assignments})
        flash("Division assignments updated!", "success")
        return redirect(url_for('league_home', league_id=league_id))
    members = []
    for u_id in league.get('user_ids', []):
        from bson import ObjectId
        user = db.users.find_one({"_id": ObjectId(u_id)})
        if user:
            members.append({"id": str(user['_id']), "username": user['username']})
    return render_template('league_assign_divisions.html', league=league, members=members, active_tab='my')

@app.route('/league/<league_id>/toggle_admin/<user_id>', methods=['POST'])
def toggle_league_admin(league_id, user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    league = db.get_league(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))
    current_user_id = session['user_id']
    if current_user_id not in league.get('administrators', []):
        flash("Unauthorized.", "error")
        return redirect(url_for('league_home', league_id=league_id))
    admins = league.get('administrators', [])
    if user_id in admins:
        if league.get('user_ids') and user_id == league['user_ids'][0]:
            flash("Safeguard: The league creator cannot be removed as an administrator.", "error")
            return redirect(url_for('league_home', league_id=league_id))
        if len(admins) <= 1:
            flash("Safeguard: Cannot remove the last league administrator.", "error")
        else:
            db.remove_administrator_from_league(league_id, user_id)
            flash("Administrator removed.", "success")
    else:
        db.add_administrator_to_league(league_id, user_id)
        flash("Administrator added.", "success")
    return redirect(url_for('league_home', league_id=league_id))

@app.route('/league/<league_id>/remove_member/<user_id>', methods=['POST'])
def remove_league_member(league_id, user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    league = db.get_league(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))
    current_user_id = session['user_id']
    if current_user_id not in league.get('administrators', []):
        flash("Unauthorized.", "error")
        return redirect(url_for('league_home', league_id=league_id))
    if league.get('user_ids') and user_id == league['user_ids'][0]:
        flash("Safeguard: The league creator cannot be removed.", "error")
    elif user_id == current_user_id:
        flash("Safeguard: You cannot remove yourself.", "error")
    else:
        db.remove_user_from_league(league_id, user_id)
        flash("Member removed from league.", "success")
    return redirect(url_for('league_home', league_id=league_id))

@app.route('/league/<league_id>/teams')
def league_teams(league_id):
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))
    all_members = {}
    all_points = get_all_player_data(league_id)
    slots = get_league_roster_slots(league)
    for u_id in league.get('user_ids', []):
        from bson import ObjectId
        user = db.users.find_one({"_id": ObjectId(u_id)})
        if user:
            roster = db.get_roster(u_id, league_id)
            player_ids = roster.get('player_ids', []) if roster else []
            players_map = {}
            for p_id in player_ids:
                p = db.players.find_one({"id": p_id})
                if p:
                    p['points'] = all_points.get(p_id, {}).get('points', 0.0)
                    players_map[p_id] = p
            starter_ids = roster.get('starters', {}) if roster else {}
            roster_starters = {slot: players_map.get(starter_ids.get(slot)) for slot in slots}
            assigned_ids = set(starter_ids.values())
            bench_players = [p for pid, p in players_map.items() if pid not in assigned_ids]
            pos_order = {"QB": 0, "RB": 1, "FB": 2, "WR": 3, "TE": 4, "K": 5}
            bench_players.sort(key=lambda x: pos_order.get(x.get('position'), 99))
            user['starters'] = roster_starters
            user['bench'] = bench_players
            user['total_points'] = round(sum(p['points'] for p in roster_starters.values() if p), 2)
            user['team_name'] = (roster.get('team', {}).get('name') if roster else None) or user['username']
            all_members[u_id] = user
    grouped_teams = []
    assigned_user_ids = set()
    if league.get('has_divisions'):
        assignments = league.get('division_assignments', {})
        names = league.get('division_names', [])
        for i, name in enumerate(names):
            div_key = str(i)
            member_ids = assignments.get(div_key, [])
            div_members = []
            for m_id in member_ids:
                if m_id in all_members:
                    div_members.append(all_members[m_id])
                    assigned_user_ids.add(m_id)
            grouped_teams.append({"name": name, "members": div_members})
    tbd_members = [u for u_id, u in all_members.items() if u_id not in assigned_user_ids]
    if tbd_members:
        grouped_teams.append({"name": "TBD" if league.get('has_divisions') else "League Members", "members": tbd_members})
    return render_template('league_teams.html', league=league, is_admin=is_admin, grouped_teams=grouped_teams, view_mode=request.args.get('view', 'divisions'))

@app.route('/league/<league_id>/standings')
def league_standings(league_id):
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))
    season = league.get('current_season', 2026)
    all_points_data = get_all_player_data(league_id)
    slots = get_league_roster_slots(league)
    all_matchups = db.get_all_league_matchups(league_id, season)
    standings_data = {}
    for u_id in league.get('user_ids', []):
        from bson import ObjectId
        user = db.users.find_one({"_id": ObjectId(u_id)})
        if not user: continue
        roster = db.get_roster(u_id, league_id)
        team_name = (roster.get('team', {}).get('name') if roster else None) or user['username']
        standings_data[u_id] = {
            "user_id": u_id, "username": user['username'], "team_name": team_name,
            "points_for": 0.0, "points_against": 0.0, "wins": 0, "losses": 0, "ties": 0, "pct": 0.0
        }
    def get_weekly_score(u_id, week_num):
        roster = db.get_roster(u_id, league_id)
        if not roster: return 0.0
        starter_ids = roster.get('starters', {})
        return round(sum(all_points_data.get(starter_ids.get(slot), {}).get('points', 0.0) for slot in slots), 2)
    for m in all_matchups:
        if m['status'] == 'scheduled':
            h_id, a_id = m['home_id'], m['away_id']
            h_score = get_weekly_score(h_id, m['week_number'])
            a_score = get_weekly_score(a_id, m['week_number'])
            for uid, my_score, opp_score in [(h_id, h_score, a_score), (a_id, a_score, h_score)]:
                if uid in standings_data:
                    standings_data[uid]['points_for'] += my_score
                    standings_data[uid]['points_against'] += opp_score
                    if my_score > opp_score: standings_data[uid]['wins'] += 1
                    elif opp_score > my_score: standings_data[uid]['losses'] += 1
                    else: standings_data[uid]['ties'] += 1
    for s in standings_data.values():
        total = s['wins'] + s['losses'] + s['ties']
        s['pct'] = (s['wins'] + 0.5 * s['ties']) / total if total > 0 else 0.0
        s['points_for'] = round(s['points_for'], 2)
    grouped_standings = []
    if league.get('has_divisions'):
        for i, name in enumerate(league.get('division_names', [])):
            div_teams = [standings_data[m_id] for m_id in league.get('division_assignments', {}).get(str(i), []) if m_id in standings_data]
            div_teams.sort(key=lambda x: (x['pct'], x['points_for']), reverse=True)
            grouped_standings.append({"name": name, "teams": div_teams})
    else:
        all_teams = sorted(standings_data.values(), key=lambda x: (x['pct'], x['points_for']), reverse=True)
        grouped_standings.append({"name": "League Standings", "teams": all_teams})
    return render_template('league_standings.html', league=league, is_admin=is_admin, grouped_standings=grouped_standings)

@app.route('/league/<league_id>/matchups')
def league_matchups(league_id):
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))
    season = league.get('current_season', 2026)
    week = int(request.args.get('week', 1))
    matchups = db.get_league_matchups(league_id, week, season)
    all_points = get_all_player_data(league_id, week=week)
    slots = get_league_roster_slots(league)
    for m in matchups:
        for side in ['home', 'away']:
            u_id = m[f'{side}_id']
            from bson import ObjectId
            user = db.users.find_one({"_id": ObjectId(u_id)})
            roster = db.get_roster(u_id, league_id)
            m[f'{side}_name'] = (roster.get('team', {}).get('name') if roster else None) or user['username']
            starter_ids = roster.get('starters', {}) if roster else {}
            m[f'{side}_score'] = round(sum(all_points.get(starter_ids.get(slot), {}).get('points', 0.0) for slot in slots), 2)
    return render_template('league_matchups.html', league=league, is_admin=is_admin, matchups=matchups, week=week)

@app.route('/league/<league_id>/matchup/<matchup_id>')
def league_matchup_detail(league_id, matchup_id):
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))

    from bson import ObjectId
    m = db.fantasy_matchups.find_one({"id": matchup_id, "league_id": league_id})
    if not m:
        flash("Matchup not found.", "error")
        return redirect(url_for('league_matchups', league_id=league_id))

    season = league.get('current_season', 2026)
    week = m['week_number']
    all_points = get_all_player_data(league_id, week=week)
    slots = get_league_roster_slots(league)
    salary_settings = league.get('salary_settings', {})

    def build_side(uid):
        user = db.users.find_one({"_id": ObjectId(uid)})
        roster = db.get_roster(uid, league_id)
        team_name = (roster.get('team', {}).get('name') if roster else None) or (user['username'] if user else 'Unknown')
        starter_ids = roster.get('starters', {}) if roster else {}
        players_map = {}
        for p_id in (roster.get('player_ids', []) if roster else []):
            p = db.get_player_by_id(p_id)
            if p:
                pd = all_points.get(p_id, {})
                p['points'] = round(pd.get('points', 0.0), 2)
                p['salary'] = calculate_salary(pd, salary_settings, p.get('position', 'QB'))
                players_map[p_id] = p
        lineup = []
        for slot in slots:
            p_id = starter_ids.get(slot)
            lineup.append({'slot': slot, 'player': players_map.get(p_id) if p_id else None})
        total = round(sum(row['player']['points'] for row in lineup if row['player']), 2)
        return {'team_name': team_name, 'user_id': uid, 'lineup': lineup, 'total': total}

    home = build_side(m['home_id'])
    away = build_side(m['away_id'])

    return render_template('league_matchup_detail.html',
        league=league, is_admin=is_admin,
        matchup=m, week=week,
        home=home, away=away)


@app.route('/league/<league_id>/draft')
def league_draft(league_id):
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))
    season = league.get('current_season', 2026)
    draft_state = db.get_draft_state(league_id, season)
    if not draft_state:
        return render_template('league_draft.html', league=league, is_admin=is_admin, draft_state=None)
    num_teams = len(draft_state['order'])
    current_pick = draft_state['current_pick']
    round_num = ((current_pick - 1) // num_teams) + 1
    pick_in_round = (current_pick - 1) % num_teams
    manager_id = draft_state['order'][num_teams - 1 - pick_in_round] if round_num % 2 == 0 else draft_state['order'][pick_in_round]
    on_the_clock = db.get_user_by_id(manager_id)
    all_players = db.get_all_players()
    drafted_ids = set(p['player_id'] for p in draft_state['picks'])
    all_league_rosters = list(db.rosters.find({"league_id": league_id}))
    roster_player_ids = {p_id for r in all_league_rosters for p_id in r.get('player_ids', [])}
    available_players = [p for p in all_players if p['id'] not in (drafted_ids | roster_player_ids)]
    picks_by_number = {}
    decorated_picks = []
    for p in draft_state['picks']:
        mgr = db.get_user_by_id(p['user_id'])
        player = db.get_player_by_id(p['player_id'])
        dp = {**p, "manager_name": mgr['username'] if mgr else "Unknown", "player_name": player['name'] if player else "Unknown", "player_pos": player['position'] if player else "??", "player_team": player['team'] if player else "??"}
        decorated_picks.append(dp)
        picks_by_number[p['pick_number']] = dp
    num_rounds = 15
    ordered_managers = [db.get_user_by_id(uid)['username'] for uid in draft_state['order']]
    draft_grid = []
    for r in range(1, num_rounds + 1):
        round_picks = []
        for i in range(num_teams):
            pick_num = ((r - 1) * num_teams) + i + 1
            m_idx = num_teams - 1 - i if r % 2 == 0 else i
            round_picks.append({"pick_number": pick_num, "manager_name": ordered_managers[m_idx], "player": picks_by_number.get(pick_num)})
        draft_grid.append(round_picks)
    return render_template('league_draft.html', league=league, is_admin=is_admin, draft_state=draft_state, on_the_clock=on_the_clock, available_players=available_players, round_num=round_num, pick_in_round=pick_in_round + 1, picks=decorated_picks, draft_grid=draft_grid, ordered_managers=ordered_managers)

@app.route('/league/<league_id>/draft/pick', methods=['POST'])
def make_draft_pick(league_id):
    league, is_admin = get_league_context(league_id)
    if not league: return {"success": False, "message": "League not found"}, 404
    season = league.get('current_season', 2026)
    draft_state = db.get_draft_state(league_id, season)
    player_id = request.form.get('player_id')
    user_id = request.form.get('user_id')
    db.make_draft_pick(league_id, season, user_id, player_id, draft_state['current_pick'], (draft_state['current_pick'] - 1) // len(draft_state['order']) + 1)
    return {"success": True}

@app.route('/league/<league_id>/draft/status')
def league_draft_status(league_id):
    league = db.get_league(league_id)
    if not league: return {"success": False}, 404
    season = league.get('current_season', 2026)
    draft_state = db.get_draft_state(league_id, season)
    if not draft_state: return {"status": "inactive"}
    num_teams = len(draft_state['order'])
    cp = draft_state['current_pick']
    rd = ((cp - 1) // num_teams) + 1
    pick_in_rd = (cp - 1) % num_teams
    manager_id = draft_state['order'][num_teams - 1 - pick_in_rd] if rd % 2 == 0 else draft_state['order'][pick_in_rd]
    on_the_clock = db.get_user_by_id(manager_id)
    picks = []
    for p in draft_state['picks'][-10:]:
        mgr = db.get_user_by_id(p['user_id'])
        player = db.get_player_by_id(p['player_id'])
        picks.append({"pick_number": p['pick_number'], "manager_name": mgr['username'] if mgr else "Unknown", "player_name": player['name'] if player else "Unknown", "player_pos": player['position'] if player else "??", "player_team": player['team'] if player else ""})
    return {"status": draft_state['status'], "current_pick": cp, "round_num": rd, "pick_in_round": pick_in_rd + 1, "on_the_clock_username": on_the_clock['username'] if on_the_clock else "Unknown", "on_the_clock_id": str(on_the_clock['_id']) if on_the_clock else None, "latest_picks": picks}

@app.route('/admin/settings', methods=['GET', 'POST'])
def admin_settings():
    if not session.get('is_site_admin'):
        flash("Unauthorized access.", "error")
        return redirect(url_for('index'))
    if request.method == 'POST':
        new_season = int(request.form.get('current_season', 2025))
        db.update_site_settings({"current_season": new_season})
        flash("Site settings updated successfully!", "success")
        return redirect(url_for('admin_settings'))
    settings = db.get_site_settings()
    return render_template('admin_settings.html', settings=settings, active_tab='settings')

@app.route('/league/<league_id>/roster_settings', methods=['GET', 'POST'])
def league_roster_settings(league_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))
        
    if not is_admin:
        flash("Unauthorized.", "error")
        return redirect(url_for('league_home', league_id=league_id))
        
    if request.method == 'POST':
        # Process settings update
        new_settings = []
        # Expecting inputs like group_0_name, group_0_count, group_0_positions
        group_indices = request.form.getlist('group_indices')
        
        for idx in group_indices:
            name = request.form.get(f'group_{idx}_name')
            count = int(request.form.get(f'group_{idx}_count', 0))
            positions = request.form.getlist(f'group_{idx}_positions')
            
            if count > 0 and name and positions:
                new_settings.append({
                    "name": name,
                    "count": count,
                    "positions": positions
                })
        
        db.update_league(league_id, {"roster_settings": new_settings})
        flash("Roster requirements updated successfully!", "success")
        return redirect(url_for('league_home', league_id=league_id))
        
    settings = league.get('roster_settings', [])
    return render_template('league_roster_settings.html', league=league, settings=settings, active_tab='my')

@app.route('/league/<league_id>/board')
def league_board(league_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))
    user_id = session['user_id']
    threads = db.get_threads(league_id)
    last_visited = db.get_board_last_visited(user_id, league_id)
    # Decorate threads with author name and unread status
    user_cache = {}
    def get_username(uid):
        if uid not in user_cache:
            u = db.get_user_by_id(uid)
            user_cache[uid] = u['username'] if u else 'Unknown'
        return user_cache[uid]
    for t in threads:
        t['author_name'] = get_username(t['author_id'])
        t['unread'] = last_visited is None or t['last_post_at'].replace(tzinfo=None) > last_visited.replace(tzinfo=None)
    db.mark_board_visited(user_id, league_id)
    return render_template('league_board.html', league=league, is_admin=is_admin, threads=threads)

@app.route('/league/<league_id>/board/new', methods=['GET', 'POST'])
def league_board_new_thread(league_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        if not title or not content:
            flash("Title and message are required.", "error")
            return redirect(url_for('league_board_new_thread', league_id=league_id))
        user_id = session['user_id']
        thread = db.create_thread(league_id, user_id, title, content)

        # Achievements
        db.award_achievement(user_id, 'first_word')

        thread_count = db.count_user_threads(user_id)
        if thread_count >= 5:
            db.award_achievement(user_id, 'town_crier')
        else:
            db.award_achievement(user_id, 'town_crier', progress=int(thread_count / 5 * 100))

        # Icebreaker — first thread on this league's board
        all_threads = db.get_threads(league_id)
        if len(all_threads) == 1:
            db.award_achievement(user_id, 'icebreaker')

        flash("Thread created!", "success")
        return redirect(url_for('league_board', league_id=league_id))
    return render_template('league_board_new.html', league=league, is_admin=is_admin)

@app.route('/league/<league_id>/board/<thread_id>', methods=['GET', 'POST'])
def league_board_thread(league_id, thread_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))
    thread = db.get_thread(thread_id)
    if not thread or thread['league_id'] != league_id:
        flash("Thread not found.", "error")
        return redirect(url_for('league_board', league_id=league_id))
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        if not content:
            flash("Reply cannot be empty.", "error")
            return redirect(url_for('league_board_thread', league_id=league_id, thread_id=thread_id))
        user_id = session['user_id']
        db.add_post(thread_id, user_id, content)

        # Achievements
        db.award_achievement(user_id, 'first_word')

        total_posts = db.count_user_posts(user_id)
        if total_posts >= 10:
            db.award_achievement(user_id, 'conversationalist')
        else:
            db.award_achievement(user_id, 'conversationalist', progress=int(total_posts / 10 * 100))

        # Hot Topic — thread has 10+ replies from other members
        updated_thread = db.get_thread(thread_id)
        other_replies = [p for p in updated_thread.get('posts', []) if p['author_id'] != updated_thread['author_id']]
        if len(other_replies) >= 10:
            db.award_achievement(updated_thread['author_id'], 'hot_topic')

        return redirect(url_for('league_board_thread', league_id=league_id, thread_id=thread_id) + '#latest')
    # Decorate posts with author names
    user_cache = {}
    def get_username(uid):
        if uid not in user_cache:
            u = db.get_user_by_id(uid)
            user_cache[uid] = u['username'] if u else 'Unknown'
        return user_cache[uid]
    for p in thread['posts']:
        p['author_name'] = get_username(p['author_id'])
    thread['author_name'] = get_username(thread['author_id'])
    return render_template('league_board_thread.html', league=league, is_admin=is_admin, thread=thread)

@app.route('/league/<league_id>/board/<thread_id>/delete', methods=['POST'])
def league_board_delete_thread(league_id, thread_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    league, is_admin = get_league_context(league_id)
    thread = db.get_thread(thread_id)
    if not thread or thread['league_id'] != league_id:
        flash("Thread not found.", "error")
        return redirect(url_for('league_board', league_id=league_id))
    if not is_admin and thread['author_id'] != session['user_id']:
        flash("Unauthorized.", "error")
        return redirect(url_for('league_board', league_id=league_id))
    db.delete_thread(thread_id)
    flash("Thread deleted.", "success")
    return redirect(url_for('league_board', league_id=league_id))

@app.route('/league/<league_id>/board/<thread_id>/post/<post_id>/delete', methods=['POST'])
def league_board_delete_post(league_id, thread_id, post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    league, is_admin = get_league_context(league_id)
    thread = db.get_thread(thread_id)
    if not thread or thread['league_id'] != league_id:
        flash("Thread not found.", "error")
        return redirect(url_for('league_board', league_id=league_id))
    post = next((p for p in thread['posts'] if p['id'] == post_id), None)
    if not post:
        flash("Post not found.", "error")
        return redirect(url_for('league_board_thread', league_id=league_id, thread_id=thread_id))
    if not is_admin and post['author_id'] != session['user_id']:
        flash("Unauthorized.", "error")
        return redirect(url_for('league_board_thread', league_id=league_id, thread_id=thread_id))
    db.delete_post(thread_id, post_id)
    flash("Post deleted.", "success")
    return redirect(url_for('league_board', league_id=league_id))

@app.route('/league/<league_id>/board/<thread_id>/pin', methods=['POST'])
def league_board_pin_thread(league_id, thread_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    league, is_admin = get_league_context(league_id)
    if not is_admin:
        flash("Unauthorized.", "error")
        return redirect(url_for('league_board', league_id=league_id))
    thread = db.get_thread(thread_id)
    if thread:
        db.toggle_pin_thread(thread_id, not thread.get('pinned', False))
        # Commissioner's Corner achievement
        if not thread.get('pinned', False):
            db.award_achievement(session['user_id'], 'commissioners_corner')
    return redirect(url_for('league_board', league_id=league_id))

@app.route('/league/<league_id>/rules')
def league_rules(league_id):
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))
        
    return render_template('league_rules.html', league=league, is_admin=is_admin)

@app.route('/league/<league_id>/rules/save', methods=['POST'])
def league_rules_save(league_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    league, is_admin = get_league_context(league_id)
    if not league or not is_admin:
        flash("Unauthorized.", "error")
        return redirect(url_for('league_rules', league_id=league_id))
    rules = {
        "roster": {
            "max_roster_size": int(request.form.get('max_roster_size', 15)),
            "ir_slots": int(request.form.get('ir_slots', 1)),
            "waiver_type": request.form.get('waiver_type', 'FAAB'),
            "faab_budget": int(request.form.get('faab_budget', 100)),
            "waiver_claim_window_hours": int(request.form.get('waiver_claim_window_hours', 24))
        },
        "scoring": {
            "bonus_100_rush_yards": float(request.form.get('bonus_100_rush_yards', 0)),
            "bonus_100_rec_yards": float(request.form.get('bonus_100_rec_yards', 0)),
            "bonus_300_pass_yards": float(request.form.get('bonus_300_pass_yards', 0)),
            "bonus_rush_td_40_plus": float(request.form.get('bonus_rush_td_40_plus', 0)),
            "bonus_rec_td_40_plus": float(request.form.get('bonus_rec_td_40_plus', 0)),
            "bonus_pass_td_40_plus": float(request.form.get('bonus_pass_td_40_plus', 0))
        },
        "trading": {
            "trading_enabled": request.form.get('trading_enabled') == 'on',
            "review_period_hours": int(request.form.get('review_period_hours', 48)),
            "trade_deadline_week": int(request.form.get('trade_deadline_week', 11)),
            "max_players_per_trade": int(request.form.get('max_players_per_trade', 5)),
            "veto_votes_required": int(request.form.get('veto_votes_required', 3))
        },
        "draft": {
            "draft_type": request.form.get('draft_type', 'Snake'),
            "order_method": request.form.get('order_method', 'Random'),
            "pick_time_limit_seconds": int(request.form.get('pick_time_limit_seconds', 120)),
            "autopick_enabled": request.form.get('autopick_enabled') == 'on'
        },
        "playoffs": {
            "regular_season_weeks": int(request.form.get('regular_season_weeks', 14)),
            "playoff_teams": int(request.form.get('playoff_teams', 4)),
            "seeding_method": request.form.get('seeding_method', 'Record then Points'),
            "tiebreaker": request.form.get('tiebreaker', 'Total Points For')
        },
        "conduct": {
            "collusion_policy": request.form.get('collusion_policy', ''),
            "inactive_team_policy": request.form.get('inactive_team_policy', ''),
            "commissioner_veto": request.form.get('commissioner_veto') == 'on'
        }
    }
    db.update_league(league_id, {"rules": rules})
    flash("League rules updated!", "success")
    return redirect(url_for('league_rules', league_id=league_id))

@app.route('/league/<league_id>/players')
def league_players(league_id):
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))

    current_user_id = session.get('user_id')
    
    # Get all rosters in this league
    all_rosters = list(db.rosters.find({"league_id": league_id}))
    
    # Map player_id to owner (team name/username)
    player_ownership = {}
    
    # Fetch all user info for these rosters in bulk
    user_ids = [r['user_id'] for r in all_rosters]
    from bson import ObjectId
    users_data = {str(u['_id']): u for u in db.users.find({"_id": {"$in": [ObjectId(uid) for uid in user_ids]}})}

    for roster in all_rosters:
        owner_id = roster['user_id']
        p_ids = roster.get('player_ids', [])
        
        user = users_data.get(owner_id)
        owner_name = (roster.get('team', {}).get('name') if roster.get('team') else None) or (user['username'] if user else "Unknown")
        
        for p_id in p_ids:
            player_ownership[p_id] = {
                "owner_id": owner_id,
                "owner_name": owner_name
            }

    # Fetch all players
    all_players = db.get_all_players()
    
    # Optimized: Get all player data (stats and points) for the league's current season
    all_season_data = get_all_player_data(league_id)
    
    # Decorate players with ownership info and season stats
    for player in all_players:
        p_id = player['id']
        pd = all_season_data.get(p_id, {})
        
        player['points'] = pd.get('points', 0.0)
        player['pass_yds'] = pd.get('pass_yds', 0)
        player['pass_td'] = pd.get('pass_td', 0)
        player['rush_yds'] = pd.get('rush_yds', 0)
        player['rush_td'] = pd.get('rush_td', 0)
        player['receptions'] = pd.get('receptions', 0)
        player['rec_yds'] = pd.get('rec_yds', 0)
        player['rec_td'] = pd.get('rec_td', 0)
        player['fumbles'] = pd.get('fumbles', 0)
        
        ownership = player_ownership.get(p_id)
        if ownership:
            player['owned_by'] = ownership['owner_name']
            player['owner_id'] = ownership['owner_id']
            player['is_mine'] = (ownership['owner_id'] == current_user_id)
            player['in_league'] = True
        else:
            player['owned_by'] = None
            player['is_mine'] = False
            player['in_league'] = False

    return render_template('league_players.html', 
                           league=league, 
                           players=all_players, 
                           is_admin=is_admin,
                           active_tab='players')

@app.route('/league/<league_id>/player/<player_id>')
def league_player(league_id, player_id):
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))

    player = db.get_player_by_id(player_id)
    if not player:
        flash("Player not found.", "error")
        return redirect(url_for('league_players', league_id=league_id))

    current_user_id = session.get('user_id')
    
    # Check ownership in this league
    all_rosters = list(db.rosters.find({"league_id": league_id}))
    
    player['owned_by'] = None
    player['owner_id'] = None
    player['is_mine'] = False
    player['in_league'] = False

    for roster in all_rosters:
        if player_id in roster.get('player_ids', []):
            owner_id = roster['user_id']
            from bson import ObjectId
            user = db.get_user_by_id(owner_id)
            
            player['owned_by'] = (roster.get('team', {}).get('name') if roster.get('team') else None) or (user['username'] if user else "Unknown")
            player['owner_id'] = owner_id
            player['is_mine'] = (owner_id == current_user_id)
            player['in_league'] = True
            break

    # Fetch game-by-game performance across ALL seasons
    settings = db.get_league_scoring_settings(league_id)
    all_games = list(db.db.nfl_games.find().sort([("summary.season.year", -1), ("summary.week.sequence", 1)]))
    
    seasons_data = {} # year -> { performance: [], total_points: 0.0 }
    available_seasons = []

    for game in all_games:
        year = game['summary']['season']['year']
        if year not in seasons_data:
            seasons_data[year] = {"performance": [], "total_points": 0.0}
            available_seasons.append(year)

        stats = game.get('statistics', {})
        game_entry = {
            "week": game['summary']['week']['sequence'],
            "opponent": "",
            "stats": None,
            "points": 0.0
        }
        
        found_in_game = False
        for side in ['home', 'away']:
            opp_side = 'away' if side == 'home' else 'home'
            side_stats = stats.get(side, {})
            
            # Check all categories for this player
            player_game_stats = {}
            found_this_side = False
            
            # Passing
            for p in side_stats.get('passing', {}).get('players', []):
                if p['id'] == player_id:
                    player_game_stats.update(p)
                    found_this_side = found_in_game = True
            
            # Rushing
            for p in side_stats.get('rushing', {}).get('players', []):
                if p['id'] == player_id:
                    player_game_stats.update(p)
                    found_this_side = found_in_game = True
                    
            # Receiving
            for p in side_stats.get('receiving', {}).get('players', []):
                if p['id'] == player_id:
                    player_game_stats.update(p)
                    found_this_side = found_in_game = True

            if found_this_side:
                game_entry['opponent'] = game['summary'][opp_side]['name']
                
                # Re-calculating cleanly for the row:
                row_pts = 0.0
                # Passing
                for p in side_stats.get('passing', {}).get('players', []):
                    if p['id'] == player_id:
                        row_pts += p.get('touchdowns', 0) * settings['passing']['td']
                        row_pts += p.get('yards', 0) * settings['passing']['yard']
                        row_pts += p.get('attempts', 0) * settings['passing']['attempt']
                        row_pts += p.get('completions', 0) * settings['passing']['completion']
                        row_pts += p.get('interceptions', 0) * settings['passing']['interception']
                # Rushing
                for p in side_stats.get('rushing', {}).get('players', []):
                    if p['id'] == player_id:
                        row_pts += p.get('touchdowns', 0) * settings['rushing']['td']
                        row_pts += p.get('yards', 0) * settings['rushing']['yard']
                        row_pts += p.get('attempts', 0) * settings['rushing']['attempt']
                # Receiving
                for p in side_stats.get('receiving', {}).get('players', []):
                    if p['id'] == player_id:
                        row_pts += p.get('touchdowns', 0) * settings['receiving']['td']
                        row_pts += p.get('yards', 0) * settings['receiving']['yard']
                        row_pts += p.get('receptions', 0) * settings['receiving']['reception']
                # Fumbles
                row_pts += player_game_stats.get('fumbles_lost', 0) * settings['misc']['fumble_lost']
                
                game_entry['points'] = round(row_pts, 2)
                game_entry['stats'] = player_game_stats
                seasons_data[year]['total_points'] += row_pts

        if found_in_game:
            seasons_data[year]['performance'].append(game_entry)

    # Round all season totals
    for y in seasons_data:
        seasons_data[y]['total_points'] = round(seasons_data[y]['total_points'], 2)

    # Determine default selected season
    selected_season = int(request.args.get('season', available_seasons[0] if available_seasons else league.get('current_season', 2026)))

    return render_template('league_player.html', 
                           league=league, 
                           player=player, 
                           seasons_data=seasons_data,
                           available_seasons=available_seasons,
                           selected_season=selected_season,
                           is_admin=is_admin,
                           active_tab='players')

@app.route('/league/<league_id>/team/<user_id>')
def league_team(league_id, user_id):
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))
    
    from bson import ObjectId
    manager = db.users.find_one({"_id": ObjectId(user_id)})
    if not manager:
        flash("Manager not found.", "error")
        return redirect(url_for('league_teams', league_id=league_id))
    
    # Fetch roster details
    roster_data = db.get_roster(user_id, league_id)
    player_ids = roster_data.get('player_ids', []) if roster_data else []
    team_info = roster_data.get('team') if roster_data else None
    
    # Optimized: Get all player points in a single pass for the league's specific season
    all_season_data = get_all_player_data(league_id)
    
    # Define Dynamic Lineup Slots
    slots = get_league_roster_slots(league)
    roster_starters = {slot: None for slot in slots}
    bench_players = []
    
    # Current Starter Assignments from DB
    starter_ids = roster_data.get('starters', {}) if roster_data else {}
    assigned_player_ids = set(starter_ids.values())

    # Map IDs to player objects
    players_map = {}
    salary_settings = league.get('salary_settings', {})
    total_roster_salary = 0
    
    for p_id in player_ids:
        p = db.players.find_one({"id": p_id})
        if p:
            pd = all_season_data.get(p_id, {})
            p['points'] = pd.get('points', 0.0)
            # Attach other stats for the specific season too
            p['pass_yds'] = pd.get('pass_yds', 0)
            p['pass_td'] = pd.get('pass_td', 0)
            p['rush_yds'] = pd.get('rush_yds', 0)
            p['rush_td'] = pd.get('rush_td', 0)
            p['receptions'] = pd.get('receptions', 0)
            
            # CALCULATE SALARY
            p['salary'] = calculate_salary(
                pd, 
                salary_settings, 
                p.get('position', 'QB')
            )
            
            total_roster_salary += p['salary']
            
            players_map[p_id] = p

    # Assign Starters
    for slot in slots:
        p_id = starter_ids.get(slot)
        if p_id and p_id in players_map:
            roster_starters[slot] = players_map[p_id]

    # Assign IR
    ir_slots_count = league.get('rules', {}).get('roster', {}).get('ir_slots', 1)
    ir_slot_names = [f"IR{i+1}" if ir_slots_count > 1 else "IR" for i in range(ir_slots_count)]
    ir_ids_map = roster_data.get('ir', {}) if roster_data else {}
    ir_assigned_ids = set(ir_ids_map.values())
    roster_ir = {}
    for ir_slot in ir_slot_names:
        p_id = ir_ids_map.get(ir_slot)
        roster_ir[ir_slot] = players_map.get(p_id) if p_id else None

    # Assign Bench (exclude IR players)
    for p_id, p in players_map.items():
        if p_id not in assigned_player_ids and p_id not in ir_assigned_ids:
            bench_players.append(p)

    # Recalculate salary excluding IR players
    total_roster_salary = sum(
        p['salary'] for p_id, p in players_map.items()
        if p_id not in ir_assigned_ids
    )

    # Sort bench by position
    pos_order = {"QB": 0, "RB": 1, "FB": 2, "WR": 3, "TE": 4, "K": 5}
    bench_players.sort(key=lambda x: pos_order.get(x.get('position'), 99))

    # Total points (Only from Starters)
    total_roster_points = round(sum(p['points'] for p in roster_starters.values() if p), 2)
    
    # Trigger scoring achievements
    if session.get('user_id') == user_id and total_roster_points >= 100:
        db.award_achievement(user_id, "high_scorer")
    if session.get('user_id') == user_id and total_roster_points >= 150:
        db.award_achievement(user_id, "sharp_shooter")
    if session.get('user_id') == user_id and total_roster_points >= 200:
        db.award_achievement(user_id, "unstoppable")
    
    # Fetch available players for search
    available_players = []
    if session.get('user_id') == user_id:
        all_players = db.get_all_players()
        excluded_player_ids = set(player_ids)
        available_players = [p for p in all_players if p['id'] not in excluded_player_ids]
    
    return render_template('league_team.html', 
                           league=league, 
                           is_admin=is_admin, 
                           manager=manager, 
                           starters=roster_starters,
                           bench=bench_players,
                           ir=roster_ir,
                           ir_slot_names=ir_slot_names,
                           total_points=total_roster_points,
                           total_salary=total_roster_salary,
                           available_players=available_players,
                           team_info=team_info)

@app.route('/league/<league_id>/team/<user_id>/salary/override', methods=['POST'])
def salary_override(league_id, user_id):
    league, is_admin = get_league_context(league_id)
    if not is_admin:
        return {"success": False, "message": "Unauthorized"}, 403
        
    player_id = request.form.get('player_id')
    new_salary = request.form.get('salary')
    
    if player_id and new_salary is not None:
        db.set_manual_salary(user_id, league_id, player_id, new_salary)
        return {"success": True}
    return {"success": False, "message": "Missing data"}, 400

@app.route('/league/<league_id>/team/<user_id>/salary/lock', methods=['POST'])
def salary_lock(league_id, user_id):
    league, is_admin = get_league_context(league_id)
    if not is_admin:
        return {"success": False, "message": "Unauthorized"}, 403
        
    player_id = request.form.get('player_id')
    lock_status = request.form.get('lock') == 'true'
    
    if player_id:
        db.toggle_salary_lock(user_id, league_id, player_id, lock_status)
        return {"success": True}
    return {"success": False, "message": "Missing data"}, 400

@app.route('/league/<league_id>/roster/move', methods=['POST'])
def league_roster_move(league_id):
    if 'user_id' not in session:
        return {"success": False, "message": "Login required"}, 401
        
    action = request.form.get('action') # 'start' or 'bench'
    player_id = request.form.get('player_id')
    slot = request.form.get('slot') # e.g. 'RB1', 'FLEX'
    
    # 1. Verify ownership and league
    roster = db.get_roster(session['user_id'], league_id)
    if not roster or player_id not in roster.get('player_ids', []):
        return {"success": False, "message": "Player not on your roster"}, 403
        
    league = db.get_league(league_id)
    if not league:
        return {"success": False, "message": "League not found"}, 404

    player = db.get_player_by_id(player_id)
    
    if action == 'start':
        # DYNAMIC POSITIONAL VALIDATION
        settings = league.get('roster_settings', [])
        valid = False
        pos = player['position']
        
        # Determine which group this slot belongs to
        target_group = None
        for group in settings:
            name = group['name']
            count = group['count']
            
            # Check if slot matches group name (single slot) or group name + number (multi slot)
            if count == 1:
                if slot == name:
                    target_group = group
                    break
            else:
                for i in range(1, count + 1):
                    if slot == f"{name}{i}":
                        target_group = group
                        break
                if target_group: break
        
        if not target_group:
            # Fallback for old leagues or mismatched slots
            return {"success": False, "message": f"Invalid slot: {slot}"}, 400
            
        if pos in target_group['positions']:
            valid = True
            
        if not valid:
            return {"success": False, "message": f"Ineligible position ({pos}) for {slot} slot (Accepts: {', '.join(target_group['positions'])})"}, 400
            
        db.set_starter(session['user_id'], league_id, player_id, slot)
        
        # Check for Roster Filler achievement
        updated_roster = db.get_roster(session['user_id'], league_id)
        starters = updated_roster.get('starters', {})
        slots = get_league_roster_slots(league)
        if all(starters.get(s) for s in slots):
            db.award_achievement(session['user_id'], "roster_filler")
        
    elif action == 'bench':
        # Find which slot this player is in and unset it
        starter_map = roster.get('starters', {})
        target_slot = None
        for s, pid in starter_map.items():
            if pid == player_id:
                target_slot = s
                break
        
        if target_slot:
            db.bench_player(session['user_id'], league_id, target_slot)

    elif action == 'ir':
        # Move player to IR slot
        ir_slot = request.form.get('slot')
        if not ir_slot:
            return {"success": False, "message": "No IR slot specified"}, 400
        ir_slots_count = league.get('rules', {}).get('roster', {}).get('ir_slots', 1)
        valid_ir = [f"IR{i+1}" if ir_slots_count > 1 else "IR" for i in range(ir_slots_count)]
        if ir_slot not in valid_ir:
            return {"success": False, "message": "Invalid IR slot"}, 400
        # Remove from starters if currently starting
        starter_map = roster.get('starters', {})
        for s, pid in starter_map.items():
            if pid == player_id:
                db.bench_player(session['user_id'], league_id, s)
                break
        db.set_ir(session['user_id'], league_id, player_id, ir_slot)
        db.log_ir_move(league_id, session['user_id'], player_id, ir_slot, 'to_ir')

    elif action == 'activate':
        # Move player off IR back to bench
        ir_slot = request.form.get('slot')
        if ir_slot:
            db.remove_ir(session['user_id'], league_id, ir_slot)
            db.log_ir_move(league_id, session['user_id'], player_id, ir_slot, 'from_ir')

    return {"success": True}

@app.route('/league/<league_id>/team/edit', methods=['GET'])
def league_team_edit(league_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))
        
    user_id = session['user_id']
    roster_data = db.get_roster(user_id, league_id)
    team_info = roster_data.get('team') if roster_data else None
    
    return render_template('league_team_edit.html', league=league, team_info=team_info)

@app.route('/league/<league_id>/trade', methods=['GET', 'POST'])
def league_trade(league_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))
        
    user_id = session['user_id']
    target_user_id = request.args.get('target_user_id')
    
    # Fetch current user's roster
    my_roster_data = db.get_roster(user_id, league_id)
    my_player_ids = my_roster_data.get('player_ids', []) if my_roster_data else []
    my_players = []
    for p_id in my_player_ids:
        p = db.players.find_one({"id": p_id})
        if p: my_players.append(p)
    
    # Order by: QB, RB, WR, TE, K
    pos_order = {"QB": 0, "RB": 1, "FB": 2, "WR": 3, "TE": 4, "K": 5}
    my_players.sort(key=lambda x: pos_order.get(x.get('position'), 99))

    my_draft_picks = []
    if my_roster_data and my_roster_data.get('team'):
        my_draft_picks = my_roster_data['team'].get('draft_picks', [])
        my_draft_picks.sort(key=lambda x: (x.get('year', 0), x.get('round', 0), x.get('pick', 0)))

    # Fetch all other teams in the league for the dropdown
    other_teams = []
    for u_id in league.get('user_ids', []):
        if u_id != user_id:
            from bson import ObjectId
            user = db.users.find_one({"_id": ObjectId(u_id)})
            if user:
                # Get team name
                roster = db.get_roster(u_id, league_id)
                team_name = roster.get('team', {}).get('name') if roster else None
                other_teams.append({
                    "id": u_id,
                    "username": user['username'],
                    "team_name": team_name or f"Team {user['username']}"
                })
    
    # Fetch target user's roster if selected
    target_players = []
    target_team_info = None
    target_draft_picks = []
    if target_user_id:
        target_roster_data = db.get_roster(target_user_id, league_id)
        target_player_ids = target_roster_data.get('player_ids', []) if target_roster_data else []
        target_team_info = target_roster_data.get('team') if target_roster_data else None
        
        if target_team_info:
            target_draft_picks = target_team_info.get('draft_picks', [])
            target_draft_picks.sort(key=lambda x: (x.get('year', 0), x.get('round', 0), x.get('pick', 0)))

        for p_id in target_player_ids:
            p = db.players.find_one({"id": p_id})
            if p: target_players.append(p)
        target_players.sort(key=lambda x: pos_order.get(x.get('position'), 99))

    # Create acronym mapping for all teams in league
    team_acronyms = {}
    league_rosters = list(db.rosters.find({"league_id": league_id}))
    for r in league_rosters:
        acronym = r.get('team', {}).get('acronym')
        if acronym:
            team_acronyms[r['user_id']] = acronym

    return render_template('league_trade.html', 
                           league=league, 
                           my_players=my_players, 
                           my_draft_picks=my_draft_picks,
                           other_teams=other_teams,
                           target_players=target_players,
                           target_draft_picks=target_draft_picks,
                           target_user_id=target_user_id,
                           target_team_info=target_team_info,
                           team_acronyms=team_acronyms)

@app.route('/league/<league_id>/trade/propose', methods=['POST'])
def propose_trade(league_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    target_user_id = request.form.get('target_user_id')
    my_raw_assets = request.form.getlist('my_assets')
    target_raw_assets = request.form.getlist('target_assets')
    
    if not target_user_id or (not my_raw_assets and not target_raw_assets):
        flash("You must select a team and at least one asset to trade.", "error")
        return redirect(url_for('league_trade', league_id=league_id, target_user_id=target_user_id))
        
    def parse_assets(raw_list):
        p_ids = []
        picks = []
        for item in raw_list:
            if item.startswith('player_'):
                p_ids.append(item.replace('player_', ''))
            elif item.startswith('pick_'):
                parts = item.split('_') # pick_teamid_year_round_pick
                if len(parts) >= 5:
                    picks.append({
                        "team_id": parts[1],
                        "year": int(parts[2]),
                        "round": int(parts[3]),
                        "pick": int(parts[4])
                    })
                else:
                    print(f"DEBUG: Invalid pick string format: {item}")
        return p_ids, picks

    my_p_ids, my_picks = parse_assets(my_raw_assets)
    target_p_ids, target_picks = parse_assets(target_raw_assets)

    trade_id = str(uuid.uuid4())
    offering_team = {
        "team_id": user_id, 
        "player_ids": my_p_ids,
        "draft_picks": my_picks
    }
    responding_team = {
        "team_id": target_user_id, 
        "player_ids": target_p_ids,
        "draft_picks": target_picks
    }
    
    db.create_trade(trade_id, league_id, offering_team, responding_team)
    flash("Trade proposal sent!", "success")
    return redirect(url_for('league_team', league_id=league_id, user_id=user_id))

@app.route('/league/<league_id>/trade/offers')
def league_trade_offers(league_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))
        
    user_id = session['user_id']
    all_trades = db.get_league_trades(league_id)
    
    # Categorize trades
    offered_trades = [] # Outgoing
    responding_trades = [] # Incoming (Must respond)
    
    for trade in all_trades:
        # Fetch manager details
        offering_manager = db.get_user_by_id(trade['team_offering']['team_id'])
        responding_manager = db.get_user_by_id(trade['team_responding']['team_id'])
        
        # Fetch team names
        offering_roster = db.get_roster(trade['team_offering']['team_id'], league_id)
        responding_roster = db.get_roster(trade['team_responding']['team_id'], league_id)
        
        trade['offering_team_name'] = (offering_roster.get('team', {}).get('name') if offering_roster else None) or offering_manager['username']
        trade['responding_team_name'] = (responding_roster.get('team', {}).get('name') if responding_roster else None) or responding_manager['username']
        
        # Fetch player details
        trade['offering_players'] = []
        for p_id in trade['team_offering'].get('player_ids', []):
            p = db.players.find_one({"id": p_id})
            if p: trade['offering_players'].append(p)
            
        trade['responding_players'] = []
        for p_id in trade['team_responding'].get('player_ids', []):
            p = db.players.find_one({"id": p_id})
            if p: trade['responding_players'].append(p)

        # Include draft picks directly (they are already structured objects)
        trade['offering_picks'] = trade['team_offering'].get('draft_picks', [])
        trade['offering_picks'].sort(key=lambda x: (x.get('year', 0), x.get('round', 0), x.get('pick', 0)))
        
        trade['responding_picks'] = trade['team_responding'].get('draft_picks', [])
        trade['responding_picks'].sort(key=lambda x: (x.get('year', 0), x.get('round', 0), x.get('pick', 0)))
            
        if trade['team_offering']['team_id'] == user_id:
            offered_trades.append(trade)
        elif trade['team_responding']['team_id'] == user_id:
            responding_trades.append(trade)
            
    # Create acronym mapping for all teams in league
    team_acronyms = {}
    league_rosters = list(db.rosters.find({"league_id": league_id}))
    for r in league_rosters:
        acronym = r.get('team', {}).get('acronym')
        if acronym:
            team_acronyms[r['user_id']] = acronym

    return render_template('league_trade_offers.html', 
                           league=league, 
                           offered_trades=offered_trades, 
                           responding_trades=responding_trades,
                           team_acronyms=team_acronyms)

@app.route('/league/<league_id>/trade/<trade_id>/accept', methods=['POST'])
def accept_trade(league_id, trade_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    trade = db.get_trade(trade_id)
    if not trade or trade['status'] != 'Pending':
        flash("Trade offer no longer valid.", "error")
        return redirect(url_for('league_trade_offers', league_id=league_id))
        
    user_id = session['user_id']
    if trade['team_responding']['team_id'] != user_id:
        flash("Unauthorized action.", "error")
        return redirect(url_for('league_trade_offers', league_id=league_id))
        
    # --- ASSET SWAP LOGIC ---
    offerer_id = trade['team_offering']['team_id']
    responder_id = trade['team_responding']['team_id']
    
    # 1. Fetch current rosters
    offerer_roster = db.get_roster(offerer_id, league_id)
    responder_roster = db.get_roster(responder_id, league_id)
    
    # 2. Swap Player IDs
    offerer_p_ids = set(offerer_roster.get('player_ids', []))
    responder_p_ids = set(responder_roster.get('player_ids', []))
    
    giving_p_ids = set(trade['team_offering'].get('player_ids', []))
    receiving_p_ids = set(trade['team_responding'].get('player_ids', []))
    
    # Remove assets being given, add assets being received
    new_offerer_p_ids = list((offerer_p_ids - giving_p_ids) | receiving_p_ids)
    new_responder_p_ids = list((responder_p_ids - receiving_p_ids) | giving_p_ids)
    
    # 3. Swap Draft Picks
    offerer_picks = offerer_roster.get('team', {}).get('draft_picks', [])
    responder_picks = responder_roster.get('team', {}).get('draft_picks', [])
    
    giving_picks = trade['team_offering'].get('draft_picks', [])
    receiving_picks = trade['team_responding'].get('draft_picks', [])
    
    def remove_picks(current_list, picks_to_remove):
        # We need to match on year, round, pick, AND original team_id
        for p_rem in picks_to_remove:
            current_list = [p for p in current_list if not (
                p.get('year') == p_rem.get('year') and 
                p.get('round') == p_rem.get('round') and 
                p.get('pick') == p_rem.get('pick') and
                p.get('team_id') == p_rem.get('team_id')
            )]
        return current_list

    new_offerer_picks = remove_picks(offerer_picks, giving_picks) + receiving_picks
    new_responder_picks = remove_picks(responder_picks, receiving_picks) + giving_picks
    
    # 4. Save Updates to Database
    db.update_roster(offerer_id, league_id, new_offerer_p_ids)
    db.update_roster(responder_id, league_id, new_responder_p_ids)
    
    # Update nested team.draft_picks
    db.rosters.update_one({"user_id": offerer_id, "league_id": league_id}, {"$set": {"team.draft_picks": new_offerer_picks}})
    db.rosters.update_one({"user_id": responder_id, "league_id": league_id}, {"$set": {"team.draft_picks": new_responder_picks}})
    
    # 5. Finalize Trade Status
    db.update_trade_status(trade_id, "Finalized")
    
    # Trigger Achievements
    db.award_achievement(offerer_id, "first_trade")
    db.award_achievement(responder_id, "first_trade")

    # Volume achievements
    for u_id in [offerer_id, responder_id]:
        total = db.count_user_finalized_trades(u_id)
        if total >= 10:
            db.award_achievement(u_id, 'trade_machine')
        elif total >= 5:
            db.award_achievement(u_id, 'deal_maker')
        else:
            db.award_achievement(u_id, 'deal_maker', progress=int(total / 5 * 100))

        # Wheelin' & Dealin' — 3 trades in this league this season
        league_total = db.count_user_finalized_trades_in_league(u_id, league_id)
        if league_total >= 3:
            db.award_achievement(u_id, 'wheelin_dealin')
        else:
            db.award_achievement(u_id, 'wheelin_dealin', progress=int(league_total / 3 * 100))

        # League Diplomat — traded with every other team
        league_obj = db.get_league(league_id)
        if league_obj:
            other_teams = set(league_obj.get('user_ids', [])) - {u_id}
            partners = db.get_user_trade_partners(u_id, league_id)
            if other_teams and other_teams.issubset(partners):
                db.award_achievement(u_id, 'league_diplomat')
            else:
                progress = int(len(partners & other_teams) / len(other_teams) * 100) if other_teams else 0
                db.award_achievement(u_id, 'league_diplomat', progress=progress)

    # Future Focused — trade includes a draft pick
    has_picks = (len(trade['team_offering'].get('draft_picks', [])) > 0 or
                 len(trade['team_responding'].get('draft_picks', [])) > 0)
    if has_picks:
        db.award_achievement(offerer_id, 'future_focused')
        db.award_achievement(responder_id, 'future_focused')

    # Asset Manager — has traded both players and picks at some point
    for u_id in [offerer_id, responder_id]:
        all_user_trades = list(db.trades.find({
            "status": "Finalized",
            "$or": [{"team_offering.team_id": u_id}, {"team_responding.team_id": u_id}]
        }))
        has_player_trade = any(
            len(t['team_offering'].get('player_ids', [])) > 0 or
            len(t['team_responding'].get('player_ids', [])) > 0
            for t in all_user_trades
        )
        has_pick_trade = any(
            len(t['team_offering'].get('draft_picks', [])) > 0 or
            len(t['team_responding'].get('draft_picks', [])) > 0
            for t in all_user_trades
        )
        if has_player_trade and has_pick_trade:
            db.award_achievement(u_id, 'asset_manager')

    # Quick Draw — responder accepted within 1 hour of trade creation
    from datetime import datetime, timezone as tz
    created = trade.get('status_modified') or trade.get('_id').generation_time
    now_utc = datetime.now(tz.utc)
    if hasattr(created, 'tzinfo') and created.tzinfo is None:
        created = created.replace(tzinfo=tz.utc)
    elapsed_hours = (now_utc - created).total_seconds() / 3600
    if elapsed_hours <= 1:
        db.award_achievement(responder_id, 'quick_draw')

    # Full Circle — responder received a player they previously traded away
    for received_id in trade['team_offering'].get('player_ids', []):
        prev = db.trades.find_one({
            "league_id": league_id,
            "status": "Finalized",
            "$or": [
                {"team_offering.team_id": responder_id, "team_offering.player_ids": received_id},
                {"team_responding.team_id": responder_id, "team_responding.player_ids": received_id}
            ]
        })
        if prev:
            db.award_achievement(responder_id, 'full_circle')
            break
    for received_id in trade['team_responding'].get('player_ids', []):
        prev = db.trades.find_one({
            "league_id": league_id,
            "status": "Finalized",
            "$or": [
                {"team_offering.team_id": offerer_id, "team_offering.player_ids": received_id},
                {"team_responding.team_id": offerer_id, "team_responding.player_ids": received_id}
            ]
        })
        if prev:
            db.award_achievement(offerer_id, 'full_circle')
            break
    
    flash("Trade successful! Your roster and draft picks have been updated.", "success")
    return redirect(url_for('league_team', league_id=league_id, user_id=user_id))

@app.route('/league/<league_id>/trade/<trade_id>/reject', methods=['POST'])
def reject_trade(league_id, trade_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    trade = db.get_trade(trade_id)
    if not trade:
        flash("Trade offer not found.", "error")
        return redirect(url_for('league_trade_offers', league_id=league_id))
        
    user_id = session['user_id']
    # Allow either party to cancel/reject? Usually only respondent can reject, offerer can cancel.
    # For now, let's just let the respondent reject.
    if trade['team_responding']['team_id'] != user_id:
        flash("Unauthorized.", "error")
        return redirect(url_for('league_trade_offers', league_id=league_id))
        
    db.update_trade_status(trade_id, "Rejected")
    flash("Trade proposal rejected.", "info")
    return redirect(url_for('league_trade_offers', league_id=league_id))

@app.route('/league/<league_id>/trade/<trade_id>/cancel', methods=['POST'])
def cancel_trade(league_id, trade_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    trade = db.get_trade(trade_id)
    if not trade:
        flash("Trade proposal not found.", "error")
        return redirect(url_for('league_trade_offers', league_id=league_id))
        
    user_id = session['user_id']
    # Only the offerer can cancel
    if trade['team_offering']['team_id'] != user_id:
        flash("Unauthorized.", "error")
        return redirect(url_for('league_trade_offers', league_id=league_id))
        
    db.update_trade_status(trade_id, "Cancelled")
    flash("Trade proposal cancelled.", "info")
    return redirect(url_for('league_trade_offers', league_id=league_id))

@app.route('/league/<league_id>/update_team', methods=['POST'])
def update_team_info(league_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    team_name = request.form.get('team_name')
    acronym = request.form.get('acronym')
    fight_song = request.form.get('fight_song')
    
    db.update_fantasy_team_info(user_id, league_id, team_name, acronym, fight_song)
    flash("Team information updated successfully!", "success")
    return redirect(url_for('league_team', league_id=league_id, user_id=user_id))

@app.route('/league/<league_id>/important_dates', methods=['POST'])
def league_important_dates(league_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    league, is_admin = get_league_context(league_id)
    if not league or not is_admin:
        flash("Unauthorized.", "error")
        return redirect(url_for('league_home', league_id=league_id))

    db.update_league(league_id, {"important_dates": {
        "draft_date": request.form.get('draft_date') or None,
        "trading_deadline": request.form.get('trading_deadline') or None,
        "roster_lock": request.form.get('roster_lock') or None,
        "playoffs_start": request.form.get('playoffs_start') or None,
        "season_end": request.form.get('season_end') or None,
        "notes": request.form.get('notes', '')
    }})
    flash("Important dates updated!", "success")
    return redirect(url_for('league_home', league_id=league_id))

@app.route('/delete_league/<league_id>', methods=['POST'])
def delete_league(league_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    league = db.get_league(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))
        
    # Only the creator (first member) can delete
    if league['user_ids'] and session['user_id'] == league['user_ids'][0]:
        db.delete_league(league_id)
        flash(f"League '{league['name']}' deleted successfully.", "success")
    else:
        flash("You are not authorized to delete this league.", "error")
        
    return redirect(url_for('leagues'))

@app.route('/team/<team_alias>')
def team_roster(team_alias):
    # Fetch team info from nfl_teams
    team_info = db.db.nfl_teams.find_one({"alias": team_alias})
    if not team_info:
        flash("Team not found.", "error")
        return redirect(url_for('nfl'))
    
    # Fetch all players for this team (match by full market + name)
    full_team_name = f"{team_info['market']} {team_info['name']}"
    team_players = list(db.players.find({"team": full_team_name}))
    
    # Sort players by position
    pos_order = {"QB": 0, "RB": 1, "FB": 2, "WR": 3, "TE": 4, "K": 5}
    team_players.sort(key=lambda x: pos_order.get(x.get('position'), 99))
    
    return render_template('team.html', team=team_info, players=team_players)

@app.route('/add_player/<player_id>')
@app.route('/add_player/<player_id>/<league_id>')
def add_player(player_id, league_id=None):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    roster_data = db.get_roster(user_id, league_id)
    player_ids = roster_data.get('player_ids', []) if roster_data else []

    if player_id not in player_ids:
        # Enforce max roster size
        if league_id:
            league = db.get_league(league_id)
            max_size = league.get('rules', {}).get('roster', {}).get('max_roster_size', 15) if league else 15
            if len(player_ids) >= max_size:
                flash(f"Roster full. Maximum roster size is {max_size} players.", "error")
                return redirect(url_for('league_team', league_id=league_id, user_id=user_id))
        player_ids.append(player_id)
        db.update_roster(user_id, league_id, player_ids)
        flash("Player added to roster.", "success")

        # Roster achievements
        db.award_achievement(user_id, 'first_pick')
        if len(player_ids) >= 10:
            db.award_achievement(user_id, 'depth_chart')
        # Waiver Hawk — track adds per league per season using roster size as proxy
        if league_id:
            total_adds = len(player_ids)
            if total_adds >= 5:
                db.award_achievement(user_id, 'waiver_hawk')
            else:
                db.award_achievement(user_id, 'waiver_hawk', progress=int(total_adds / 5 * 100))
    else:
        flash("Player already in roster.", "info")

    if league_id:
        return redirect(url_for('league_team', league_id=league_id, user_id=user_id))
    return redirect(url_for('nfl_players'))

@app.route('/remove_player/<player_id>')
@app.route('/remove_player/<player_id>/<league_id>')
def remove_player(player_id, league_id=None):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    roster_data = db.get_roster(user_id, league_id)
    if roster_data:
        player_ids = roster_data.get('player_ids', [])
        if player_id in player_ids:
            player_ids.remove(player_id)
            db.update_roster(user_id, league_id, player_ids)
            if league_id:
                db.log_drop(league_id, user_id, player_id)
            flash("Player removed from roster.", "success")

    if league_id:
        return redirect(url_for('league_team', league_id=league_id, user_id=user_id))
    return redirect(url_for('leagues_my'))

@app.route('/freeze_roster', methods=['POST'])
def freeze_roster():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    roster_data = db.get_roster(user_id)

    if not roster_data or not roster_data.get('player_ids'):
        flash("Cannot freeze an empty roster.", "error")
        return redirect(url_for('leagues'))

    player_ids = roster_data['player_ids']
    current_week = 1  # Default for 2026 Season

    db.freeze_roster(user_id, player_ids, current_week)
    flash(f"Roster frozen for Week {current_week}!", "success")
    return redirect(url_for('leagues'))

@app.before_request
def check_announcements():
    if 'user_id' in session and request.endpoint not in ['static', 'logout', 'mark_announcement_read']:
        from flask import g
        user = db.get_user_by_id(session['user_id'])
        if user and user.get('announcements'):
            # Find the first unread announcement
            unread = next((a for a in user['announcements'] if not a.get('heard')), None)
            if unread:
                # Fetch the actual message from the announcements collection
                announcement_data = db.announcements.find_one({"id": unread['announcement_id']})
                if announcement_data:
                    g.unread_announcement = announcement_data

@app.route('/announcement/read/<announcement_id>', methods=['POST'])
def mark_announcement_read(announcement_id):
    if 'user_id' not in session:
        return {"success": False, "message": "Not logged in"}, 401
    
    # Check if this is a GodSpeak announcement before marking as heard
    announcement = db.announcements.find_one({"id": announcement_id})
    if announcement and announcement.get('type') == 'GodSpeak':
        db.award_achievement(session['user_id'], "god_listener")
    
    db.mark_announcement_as_heard(session['user_id'], announcement_id)
    return {"success": True}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
