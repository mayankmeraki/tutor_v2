import asyncio, certifi, os
from dotenv import load_dotenv
load_dotenv('.env')
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient(os.environ['MONGODB_URI'], tlsCAFile=certifi.where(), serverSelectionTimeoutMS=10000)
    db = client['tutor_v2']

    user = await db.users.find_one({"email": "usefulcontent25@gmail.com"})
    if user:
        print(f"Name: {user.get('name')}")
        print(f"Email: {user.get('email')}")
        print(f"Signed up: {user.get('createdAt')}")
    else:
        print("User not found")

    sessions = await db.sessions.find(
        {"userEmail": "usefulcontent25@gmail.com"},
        {"title": 1, "headline": 1, "createdAt": 1, "durationSec": 1,
         "metrics": 1, "intent": 1, "status": 1, "teachingMode": 1,
         "transcript.timestamp": 1, "transcript.role": 1, "transcript.content": 1},
    ).sort("createdAt", -1).to_list(length=50)

    print(f"\nTotal sessions: {len(sessions)}")
    total_turns = 0
    total_student = 0
    topics = []
    for i, s in enumerate(sessions):
        m = s.get("metrics", {})
        turns = m.get("totalTurns", 0)
        student = m.get("studentResponses", 0)
        total_turns += turns
        total_student += student
        intent = s.get("intent", {})
        raw = intent.get("raw", "") if isinstance(intent, dict) else str(intent)
        title = s.get("title") or s.get("headline") or raw[:60] or "(no title)"
        topics.append(title)
        print(f"  {i+1}. {title}")
        print(f"     {str(s.get('createdAt',''))[:19]} | {turns} turns ({student} student) | {s.get('status','?')}")

    print(f"\nSummary: {len(sessions)} sessions, {total_turns} total turns, {total_student} student messages")
    print(f"Topics: {', '.join(topics[:10])}")

    client.close()

asyncio.run(main())
