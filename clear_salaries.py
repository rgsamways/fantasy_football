from database import Database
db = Database()
result = db.rosters.update_many({}, {"$unset": {"manual_salaries": "", "locked_salaries": ""}})
print(f"Modified {result.modified_count} rosters.")
