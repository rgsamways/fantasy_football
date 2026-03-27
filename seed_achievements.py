from database import Database

def seed_achievements():
    db = Database()
    
    achievements = [
        {
            "id": "first_trade",
            "name": "The Architect",
            "description": "Complete your first trade proposal and finalize a deal.",
            "icon": "🤝",
            "category": "Trading"
        },
        {
            "id": "deal_maker",
            "name": "Deal Maker",
            "description": "Complete 5 trades total across all leagues.",
            "icon": "📦",
            "category": "Trading"
        },
        {
            "id": "trade_machine",
            "name": "Trade Machine",
            "description": "Complete 10 trades total across all leagues.",
            "icon": "🏥",
            "category": "Trading"
        },
        {
            "id": "wheelin_dealin",
            "name": "Wheelin' & Dealin'",
            "description": "Complete 3 trades in a single season within the same league.",
            "icon": "🤑",
            "category": "Trading"
        },
        {
            "id": "quick_draw",
            "name": "Quick Draw",
            "description": "Accept a trade offer within 1 hour of receiving it.",
            "icon": "⚡",
            "category": "Trading"
        },
        {
            "id": "future_focused",
            "name": "Future Focused",
            "description": "Complete a trade that includes at least one draft pick.",
            "icon": "🔮",
            "category": "Trading"
        },
        {
            "id": "asset_manager",
            "name": "Asset Manager",
            "description": "Complete trades involving both players and draft picks across your career.",
            "icon": "🧠",
            "category": "Trading"
        },
        {
            "id": "buy_low",
            "name": "Buy Low",
            "description": "Acquire a player via trade who scores 20+ points the following week.",
            "icon": "📈",
            "category": "Trading"
        },
        {
            "id": "mutual_benefit",
            "name": "Mutual Benefit",
            "description": "Both teams in one of your trades finish the season with a winning record.",
            "icon": "🤝",
            "category": "Trading"
        },
        {
            "id": "full_circle",
            "name": "Full Circle",
            "description": "Trade away a player and then trade for that same player again later.",
            "icon": "🔄",
            "category": "Trading"
        },
        {
            "id": "league_diplomat",
            "name": "League Diplomat",
            "description": "Complete a trade with every other team in your league at least once.",
            "icon": "🌐",
            "category": "Trading"
        },
        {
            "id": "fair_dealer",
            "name": "Fair Dealer",
            "description": "Go an entire season with no trades rejected or cancelled.",
            "icon": "⚖️",
            "category": "Trading"
        },
        {
            "id": "high_scorer",
            "name": "Century Club",
            "description": "Score 100+ points in a single week with your starting lineup.",
            "icon": "💯",
            "category": "Scoring"
        },
        {
            "id": "sharp_shooter",
            "name": "Sharp Shooter",
            "description": "Score 150 or more points in a single week with your starting lineup.",
            "icon": "🎯",
            "category": "Scoring"
        },
        {
            "id": "unstoppable",
            "name": "Unstoppable",
            "description": "Score 200 or more points in a single week with your starting lineup.",
            "icon": "🚀",
            "category": "Scoring"
        },
        {
            "id": "on_a_roll",
            "name": "On a Roll",
            "description": "Score 100+ points in 3 consecutive weeks in the same league.",
            "icon": "📈",
            "category": "Scoring"
        },
        {
            "id": "shutout",
            "name": "Shutout",
            "description": "Win a matchup where your opponent scores fewer than 50 points.",
            "icon": "💀",
            "category": "Scoring"
        },
        {
            "id": "season_dominator",
            "name": "Season Dominator",
            "description": "Finish the regular season with the highest total points for in your league.",
            "icon": "🏆",
            "category": "Scoring"
        },
        {
            "id": "league_pioneer",
            "name": "League Pioneer",
            "description": "Join your first fantasy league.",
            "icon": "🚀",
            "category": "General"
        },
        {
            "id": "pull_the_shades_down",
            "name": "Pull The Shades Down",
            "description": "Switch to dark mode for the first time.",
            "icon": "🌙",
            "category": "General"
        },
        {
            "id": "team_spirit",
            "name": "Team Spirit",
            "description": "Apply an NFL team's colors to the app for the first time.",
            "icon": "🏈",
            "category": "General"
        },
        {
            "id": "roster_filler",
            "name": "Full House",
            "description": "Have a player in every starting roster slot.",
            "icon": "🏠",
            "category": "Roster"
        },
        {
            "id": "first_pick",
            "name": "First Pick",
            "description": "Add your first player to a roster.",
            "icon": "🎯",
            "category": "Roster"
        },
        {
            "id": "depth_chart",
            "name": "Depth Chart",
            "description": "Have at least 10 players on your roster at the same time.",
            "icon": "📋",
            "category": "Roster"
        },
        {
            "id": "elite_squad",
            "name": "Elite Squad",
            "description": "Have 3 or more players on your roster who each scored 100+ points in a season.",
            "icon": "💎",
            "category": "Roster"
        },
        {
            "id": "waiver_hawk",
            "name": "Waiver Hawk",
            "description": "Add 5 or more players to your roster in a single season.",
            "icon": "🔍",
            "category": "Roster"
        },
        {
            "id": "instant_upgrade",
            "name": "Instant Upgrade",
            "description": "Add a player who scores 20+ points the very next week after being added.",
            "icon": "⚡",
            "category": "Roster"
        },
        {
            "id": "perfect_lineup",
            "name": "Perfect Lineup",
            "description": "Have every starter score at least 10 points in a single week.",
            "icon": "🧩",
            "category": "Roster"
        },
        {
            "id": "bench_warmer",
            "name": "Bench Warmer",
            "description": "Have a bench player outscore all of your starters in a single week.",
            "icon": "🎰",
            "category": "Roster"
        },
        {
            "id": "rotation_master",
            "name": "Rotation Master",
            "description": "Start a different player in the same roster slot 3 weeks in a row.",
            "icon": "🔄",
            "category": "Roster"
        },
        {
            "id": "qb_whisperer",
            "name": "QB Whisperer",
            "description": "Have a QB on your roster score 40+ points in a single week.",
            "icon": "🏈",
            "category": "Roster"
        },
        {
            "id": "backfield_boss",
            "name": "Backfield Boss",
            "description": "Have 2 RBs on your roster each score 20+ points in the same week.",
            "icon": "🏃",
            "category": "Roster"
        },
        {
            "id": "receiving_corps",
            "name": "Receiving Corps",
            "description": "Have 3 WRs on your roster each score 15+ points in the same week.",
            "icon": "🎯",
            "category": "Roster"
        },
        {
            "id": "god_listener",
            "name": "God-Speak Listener",
            "description": "Hear a message broadcast by a God user.",
            "icon": "👂",
            "category": "Social"
        },
        {
            "id": "weekly_mvp",
            "name": "Weekly MVP",
            "description": "Have the highest scoring team across all leagues in a single week.",
            "icon": "👑",
            "category": "Competitive"
        },
        {
            "id": "perfect_month",
            "name": "Perfect Month",
            "description": "Go 4-0 in your league matchups over a 4-week span.",
            "icon": "🌟",
            "category": "Competitive"
        },
        {
            "id": "hot_streak",
            "name": "Hot Streak",
            "description": "Win 3 matchups in a row in the same league.",
            "icon": "🔥",
            "category": "Competitive"
        },
        {
            "id": "unstoppable_force",
            "name": "Unstoppable Force",
            "description": "Win 5 matchups in a row in the same league.",
            "icon": "⚡",
            "category": "Competitive"
        },
        {
            "id": "ironman",
            "name": "Ironman",
            "description": "Complete a full regular season with a full starting lineup set every week.",
            "icon": "💪",
            "category": "Competitive"
        },
        {
            "id": "regular_season_champ",
            "name": "Regular Season Champ",
            "description": "Finish 1st in your league's regular season standings.",
            "icon": "🥇",
            "category": "Competitive"
        },
        {
            "id": "podium_finish",
            "name": "Podium Finish",
            "description": "Finish in the top 3 of your league's regular season standings.",
            "icon": "🏅",
            "category": "Competitive"
        },
        {
            "id": "comeback_kid",
            "name": "Comeback Kid",
            "description": "Be in last place after week 4 and finish the regular season in the top half.",
            "icon": "📉",
            "category": "Competitive"
        },
        {
            "id": "dominant_victory",
            "name": "Dominant Victory",
            "description": "Win a matchup by 50 or more points.",
            "icon": "😤",
            "category": "Competitive"
        },
        {
            "id": "nail_biter",
            "name": "Nail Biter",
            "description": "Win a matchup by fewer than 5 points.",
            "icon": "🤏",
            "category": "Competitive"
        },
        {
            "id": "precision",
            "name": "Precision",
            "description": "Win exactly 7 of your 14 regular season matchups.",
            "icon": "🎯",
            "category": "Competitive"
        },
        {
            "id": "champion",
            "name": "Champion",
            "description": "Win your league's championship.",
            "icon": "👑",
            "category": "Competitive"
        },
        {
            "id": "runner_up",
            "name": "Runner Up",
            "description": "Finish 2nd in your league's championship.",
            "icon": "🥈",
            "category": "Competitive"
        },
        {
            "id": "first_word",
            "name": "First Word",
            "description": "Post your first message on any league board.",
            "icon": "🗣️",
            "category": "Social"
        },
        {
            "id": "conversationalist",
            "name": "Conversationalist",
            "description": "Post 10 replies across any league boards.",
            "icon": "💬",
            "category": "Social"
        },
        {
            "id": "town_crier",
            "name": "Town Crier",
            "description": "Create 5 threads across any leagues.",
            "icon": "📢",
            "category": "Social"
        },
        {
            "id": "hot_topic",
            "name": "Hot Topic",
            "description": "Create a thread that receives 10 or more replies from other members.",
            "icon": "🔥",
            "category": "Social"
        },
        {
            "id": "icebreaker",
            "name": "Icebreaker",
            "description": "Be the first person to post on a brand new league's board.",
            "icon": "🤝",
            "category": "Social"
        },
        {
            "id": "commissioners_corner",
            "name": "Commissioner's Corner",
            "description": "Pin your first thread as a league administrator.",
            "icon": "📌",
            "category": "Social"
        }
    ]
    
    # Clear existing and re-seed
    db.db.achievement_definitions.delete_many({})
    db.db.achievement_definitions.insert_many(achievements)
    print(f"Successfully seeded {len(achievements)} achievements.")

if __name__ == "__main__":
    seed_achievements()
