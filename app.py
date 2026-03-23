import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, flash
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

@app.route('/admin')
def admin_panel():
    if not session.get('is_site_admin'):
        flash("Unauthorized access.", "error")
        return redirect(url_for('index'))
    
    # Fetch some basic stats for the admin page
    user_count = db.users.count_documents({})
    league_count = db.leagues.count_documents({})
    player_count = db.players.count_documents({})
    
    return render_template('admin_dashboard.html', 
                           user_count=user_count, 
                           league_count=league_count, 
                           player_count=player_count,
                           active_tab='dashboard')

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

        update_data = {
            "email": new_email
        }

        db.update_user(user_id, update_data)
        flash("Profile updated successfully!", "success")
        return redirect(url_for('profile_details'))

    user = db.get_user_by_id(user_id)
    return render_template('profile_details_edit.html', user=user, active_tab='details')

@app.route('/profile/achievements')
def profile_achievements():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('profile_achievements.html', active_tab='achievements')

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
            # Create the announcement
            result = db.create_announcement(announcement_type="GodSpeak", message=message, user_id=str(user['_id']))
            announcement_id = db.announcements.find_one({"_id": result.inserted_id})['id']
            
            # Add to all users (this is a broadcast)
            # Note: For performance in large apps we'd handle this differently, 
            # but for this scale we can push to all user docs.
            db.users.update_many({}, {"$push": {"announcements": {
                "announcement_id": announcement_id,
                "heard": False,
                "heard_at": None
            }}})
            
            flash("The masses have heard your word.", "success")
            return redirect(url_for('profile_details'))

    return render_template('speak.html', active_tab='details')

@app.route('/nfl')
def nfl():
    return redirect(url_for('nfl_home'))

@app.route('/nfl/home')
def nfl_home():
    return render_template('nfl_home.html', active_tab='home')

@app.route('/nfl/teams')
def nfl_teams():
    teams = db.get_all_teams()
    
    # Group teams by conference and division
    conferences = {}
    for team in teams:
        conf = team.get('conference')
        div = team.get('division')
        
        if conf not in conferences:
            conferences[conf] = {}
        
        if div not in conferences[conf]:
            conferences[conf][div] = []
            
        conferences[conf][div].append(team)
    
    # Sort divisions within each conference
    for conf in conferences:
        conferences[conf] = dict(sorted(conferences[conf].items()))
        
    return render_template('nfl_teams.html', conferences=conferences, active_tab='teams')

@app.route('/nfl/players')
def nfl_players():
    all_players = db.get_all_players()
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
    return render_template('nfl_standings.html', active_tab='standings')

@app.route('/nfl/schedule')
def nfl_schedule():
    return render_template('nfl_schedule.html', active_tab='schedule')

@app.route('/nfl/team/<team_alias>')
def nfl_team(team_alias):
    # Fetch team info from teams_meta
    team_info = db.db.teams_meta.find_one({"alias": team_alias})
    if not team_info:
        flash("Team not found.", "error")
        return redirect(url_for('nfl_teams'))
    
    # Fetch all players for this team (match by full market + name)
    full_team_name = f"{team_info['market']} {team_info['name']}"
    team_players = list(db.players.find({"team": full_team_name}))

    # Sort players by position
    pos_order = {"QB": 0, "RB": 1, "FB": 2, "WR": 3, "TE": 4, "K": 5}
    team_players.sort(key=lambda x: pos_order.get(x.get('position'), 99))

    return render_template('nfl_team.html', team=team_info, players=team_players, active_tab='teams')

@app.route('/nfl/rumors')
def nfl_rumors():
    return render_template('nfl_rumors.html', active_tab='rumors')

@app.route('/leagues')
def leagues():
    return redirect(url_for('leagues_my'))

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
        
        # Initialize draft picks for creator
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
    # Filter leagues where user_id is in the user_ids array
    my_leagues = list(db.leagues.find({"user_ids": user_id}))
    return render_template('leagues_my.html', leagues=my_leagues, active_tab='my')

@app.route('/leagues/public')
def leagues_public():
    # Showing all leagues for now as "public"
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
    
    # Initialize draft picks for joining member
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
    
    # Update last visited timestamp for logged in user
    if 'user_id' in session:
        db.update_user_last_visited(session['user_id'])
    
    # Fetch member details
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
            # Get roster count
            roster = db.get_roster(u_id, league_id)
            roster_count = len(roster.get('player_ids', [])) if roster else 0
            
            # Check if frozen for current week (default week 1)
            frozen = db.get_frozen_roster(u_id, 1) is not None
            
            # Format last visited timestamp for JS to handle timezone
            last_visited = user.get('last_visited')
            iso_visited = None
            if last_visited:
                # Ensure it's treated as UTC by appending Z if offset is missing
                iso_visited = last_visited.isoformat()
                if not iso_visited.endswith('Z') and '+' not in iso_visited:
                    iso_visited += 'Z'

            # Get team name from roster if it exists
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
            
    return render_template('league_home.html', league=league, members=members, is_admin=is_admin)

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
            "num_divisions": new_num_divisions
        }

        # Handle division_names array maintenance
        if has_divisions and new_num_divisions:
            current_names = league.get('division_names', [])
            current_assignments = league.get('division_assignments', {})
            
            new_assignments = {}
            if len(current_names) < new_num_divisions:
                # Add new default names and empty assignments
                for i in range(len(current_names), new_num_divisions):
                    current_names.append(f"Division {i+1}")
                
                # Keep existing assignments, add new ones
                for i in range(new_num_divisions):
                    new_assignments[str(i)] = current_assignments.get(str(i), [])
            elif len(current_names) > new_num_divisions:
                # Truncate names
                current_names = current_names[:new_num_divisions]
                
                # Truncate assignments (any members in deleted divisions become unassigned)
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
        
    # Fetch member details for the form
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
        
    # Only current admins can toggle others
    current_user_id = session['user_id']
    if current_user_id not in league.get('administrators', []):
        flash("Unauthorized.", "error")
        return redirect(url_for('league_home', league_id=league_id))
        
    admins = league.get('administrators', [])
    if user_id in admins:
        # Safeguard: Don't remove the league creator
        if league.get('user_ids') and user_id == league['user_ids'][0]:
            flash("Safeguard: The league creator cannot be removed as an administrator.", "error")
            return redirect(url_for('league_home', league_id=league_id))

        # Safeguard: Don't remove the last admin
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
        
    # Only current admins can remove members
    current_user_id = session['user_id']
    if current_user_id not in league.get('administrators', []):
        flash("Unauthorized.", "error")
        return redirect(url_for('league_home', league_id=league_id))
        
    # Safeguard: Don't remove the league creator or yourself through this button
    if league.get('user_ids') and user_id == league['user_ids'][0]:
        flash("Safeguard: The league creator cannot be removed.", "error")
    elif user_id == current_user_id:
        flash("Safeguard: You cannot remove yourself. To leave, use the 'Leave League' button (coming soon).", "error")
    else:
        db.remove_user_from_league(league_id, user_id)
        flash("Member removed from league.", "success")
        
    return redirect(url_for('league_home', league_id=league_id))

def get_league_context(league_id):
    league = db.get_league(league_id)
    if not league:
        return None, None
    
    is_admin = False
    current_user_id = session.get('user_id')
    if current_user_id and current_user_id in league.get('administrators', []):
        is_admin = True
    
    return league, is_admin

@app.route('/league/<league_id>/teams')
def league_teams(league_id):
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))
    
    # Fetch all member details first
    all_members = {}
    for u_id in league.get('user_ids', []):
        from bson import ObjectId
        user = db.users.find_one({"_id": ObjectId(u_id)})
        if user:
            roster = db.get_roster(u_id, league_id)
            user['roster'] = roster
            
            # Fetch player details for the roster table
            player_ids = roster.get('player_ids', []) if roster else []
            roster_players = []
            for p_id in player_ids:
                p = db.players.find_one({"id": p_id})
                if p:
                    roster_players.append(p)
            
            # Sort players by position
            pos_order = {"QB": 0, "RB": 1, "FB": 2, "WR": 3, "TE": 4, "K": 5}
            roster_players.sort(key=lambda x: pos_order.get(x.get('position'), 99))
            user['roster_players'] = roster_players
            
            all_members[u_id] = user
            
    # Group by division
    grouped_teams = [] # List of { "name": "Div Name", "members": [...] }
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
            
            grouped_teams.append({
                "name": name,
                "members": div_members
            })
            
    # TBD Section (Unassigned or No Divisions)
    tbd_members = []
    for u_id, user in all_members.items():
        if u_id not in assigned_user_ids:
            tbd_members.append(user)
            
    if tbd_members:
        grouped_teams.append({
            "name": "TBD" if league.get('has_divisions') else "League Members",
            "members": tbd_members
        })
            
    return render_template('league_teams.html', 
                           league=league, 
                           is_admin=is_admin, 
                           grouped_teams=grouped_teams,
                           view_mode=request.args.get('view', 'divisions'))

@app.route('/league/<league_id>/rules')
def league_rules(league_id):
    league, is_admin = get_league_context(league_id)
    if not league:
        flash("League not found.", "error")
        return redirect(url_for('leagues'))
        
    return render_template('league_rules.html', league=league, is_admin=is_admin)

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
    
    # Decorate players with ownership info
    for player in all_players:
        p_id = player['id']
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

    return render_template('league_player.html', 
                           league=league, 
                           player=player, 
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
    
    roster_players = []
    for p_id in player_ids:
        p = db.players.find_one({"id": p_id})
        if p:
            roster_players.append(p)

    # Order by: QB, RB, WR, TE, K
    pos_order = {"QB": 0, "RB": 1, "FB": 2, "WR": 3, "TE": 4, "K": 5}
    roster_players.sort(key=lambda x: pos_order.get(x.get('position'), 99))
    
    # Fetch available players for the player search pane (right pane)
    # Only if the viewer is the manager of this roster
    available_players = []
    if session.get('user_id') == user_id:
        all_players = db.get_all_players()
        # Exclude players already in THIS roster
        excluded_player_ids = set(player_ids)
        available_players = [p for p in all_players if p['id'] not in excluded_player_ids]
    
    return render_template('league_team.html', 
                           league=league, 
                           is_admin=is_admin, 
                           manager=manager, 
                           roster=roster_players,
                           available_players=available_players,
                           team_info=team_info)

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
    # Fetch team info from teams_meta
    team_info = db.db.teams_meta.find_one({"alias": team_alias})
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
        player_ids.append(player_id)
        db.update_roster(user_id, league_id, player_ids)
        flash("Player added to roster.", "success")
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
    
    db.mark_announcement_as_heard(session['user_id'], announcement_id)
    return {"success": True}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
