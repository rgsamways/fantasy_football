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
            "id": "high_scorer",
            "name": "Century Club",
            "description": "Score over 100 points in a single week with your starting lineup.",
            "icon": "💯",
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
            "id": "roster_filler",
            "name": "Full House",
            "description": "Have a player in every starting roster slot.",
            "icon": "🏠",
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
        }
    ]
    
    # Clear existing and re-seed
    db.db.achievement_definitions.delete_many({})
    db.db.achievement_definitions.insert_many(achievements)
    print(f"Successfully seeded {len(achievements)} achievements.")

if __name__ == "__main__":
    seed_achievements()
