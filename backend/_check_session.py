import asyncio, certifi, json
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient(
        "mongodb+srv://mayank:NWsGMchTprlN3S14@cluster0.rftqzyz.mongodb.net/",
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=10000,
    )
    db = client["tutor_v2"]

    # Grab a few sessions to inspect timing fields
    sessions = await db.sessions.find(
        {"userEmail": {"$ne": "mayank@test.com"}},
        {"userEmail": 1, "studentName": 1, "createdAt": 1, "startedAt": 1, "endedAt": 1,
         "durationSec": 1, "status": 1, "metrics": 1,
         "transcript": 1, "title": 1, "headline": 1},
    ).sort("createdAt", -1).to_list(length=5)

    for s in sessions:
        dur = s.get('durationSec') or 0
        print(f"{'='*80}")
        print(f"{s.get('studentName','?')} | {s.get('title') or s.get('headline') or '?'}")
        print(f"  createdAt:  {s.get('createdAt')}")
        print(f"  startedAt:  {s.get('startedAt')}")
        print(f"  endedAt:    {s.get('endedAt')}")
        print(f"  durationSec: {dur} ({dur//3600}h {(dur%3600)//60}m {dur%60}s)")
        print(f"  status:     {s.get('status')}")
        print(f"  metrics:    {json.dumps(s.get('metrics', {}), default=str)}")

        transcript = s.get("transcript", [])
        print(f"\n  Transcript ({len(transcript)} entries) — checking for timestamps:")
        for i, t in enumerate(transcript[:8]):
            if isinstance(t, dict):
                keys = list(t.keys())
                role = t.get("role", "?")
                ts = t.get("timestamp", t.get("createdAt", t.get("time", t.get("ts", "NONE"))))
                content = t.get("content", t.get("text", ""))
                if isinstance(content, str):
                    content = content[:80]
                elif isinstance(content, list):
                    content = "[list content]"
                print(f"    [{i}] role={role} ts={ts} keys={keys}")
                print(f"        content: {content}")
        print()

    client.close()

asyncio.run(main())
