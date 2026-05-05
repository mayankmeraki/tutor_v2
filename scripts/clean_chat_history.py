"""Clean duplicate messages from path chatHistory."""
import os, certifi
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv('backend/.env', override=True)

uri = os.environ.get('MONGODB_URI', '')
db_name = os.environ.get('MONGODB_DB', 'myprofessor')
client = MongoClient(uri, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)
db = client[db_name]

for path in db.paths.find({"chatHistory": {"$exists": True, "$ne": []}}):
    pid = path["pathId"][:12]
    history = path.get("chatHistory", [])
    if not history:
        continue

    # Deduplicate: keep only unique (role, text) pairs in order
    seen = set()
    cleaned = []
    for msg in history:
        key = (msg.get("role", ""), msg.get("text", "")[:100])
        if key not in seen:
            seen.add(key)
            cleaned.append(msg)

    removed = len(history) - len(cleaned)
    if removed > 0:
        db.paths.update_one(
            {"pathId": path["pathId"]},
            {"$set": {"chatHistory": cleaned[-50:]}},  # Keep last 50
        )
        print(f"{pid}: {len(history)} -> {len(cleaned)} ({removed} duplicates removed)")
    else:
        print(f"{pid}: {len(history)} messages (clean)")

print("Done")
