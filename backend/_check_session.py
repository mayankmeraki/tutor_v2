import asyncio, certifi, json
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient(
        "mongodb+srv://mayank:NWsGMchTprlN3S14@cluster0.rftqzyz.mongodb.net/",
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=10000,
    )
    db = client["tutor_v2"]

    # Get a session with actual interaction
    s = await db.sessions.find_one(
        {"userEmail": {"$ne": "mayank@test.com"}, "metrics.totalTurns": {"$gte": 3}},
        {"transcript": 1, "backendState.messages": 1, "studentName": 1, "title": 1, "headline": 1},
        sort=[("createdAt", -1)],
    )

    print(f"Session: {s.get('studentName')} — {s.get('title') or s.get('headline')}")

    # Check transcript structure
    transcript = s.get("transcript", [])
    print(f"\n--- transcript: {len(transcript)} entries ---")
    for i, t in enumerate(transcript[:4]):
        if isinstance(t, dict):
            role = t.get("role", "?")
            keys = list(t.keys())
            content = t.get("content", "")
            if isinstance(content, str):
                content = content[:150]
            elif isinstance(content, list):
                content = f"[list: {len(content)} blocks]"
            print(f"  [{i}] role={role} keys={keys}")
            print(f"       content: {content}")

    # Check backendState.messages structure
    bs_messages = (s.get("backendState") or {}).get("messages", [])
    print(f"\n--- backendState.messages: {len(bs_messages)} entries ---")
    for i, m in enumerate(bs_messages[:6]):
        if isinstance(m, dict):
            role = m.get("role", "?")
            keys = list(m.keys())
            content = m.get("content", "")
            if isinstance(content, str):
                preview = content[:200]
            elif isinstance(content, list):
                preview = f"[list: {len(content)} blocks — "
                for b in content[:3]:
                    if isinstance(b, dict):
                        preview += f"{b.get('type','?')}({len(str(b.get('text','')))}) "
                preview += "]"
            else:
                preview = str(content)[:150]
            print(f"  [{i}] role={role} keys={keys}")
            print(f"       content: {preview}")

    client.close()

asyncio.run(main())
