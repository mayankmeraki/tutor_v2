import asyncio, certifi
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient(
        "mongodb+srv://mayank:NWsGMchTprlN3S14@cluster0.rftqzyz.mongodb.net/",
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=10000,
    )
    db = client["tutor_v2"]
    cursor = db.users.find({"name": {"$regex": "peeyush", "$options": "i"}})
    results = await cursor.to_list(length=100)
    if results:
        for u in results:
            print("FOUND:")
            print(f"  _id:       {u['_id']}")
            print(f"  name:      {u.get('name')}")
            print(f"  email:     {u.get('email')}")
            print(f"  role:      {u.get('role')}")
            print(f"  createdAt: {u.get('createdAt')}")
    else:
        print('No user named "peeyush" found.')

    print(f"\nTotal users in tutor_v2.users: {await db.users.count_documents({})}")
    print("\nAll users:")
    async for u in db.users.find({}, {"name": 1, "email": 1}):
        print(f"  {u.get('name')} | {u.get('email')}")

    client.close()

asyncio.run(main())
