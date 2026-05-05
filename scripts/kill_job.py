"""Kill a stuck BYO job."""
import os, certifi
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv('backend/.env', override=True)

uri = os.environ.get('MONGODB_URI', '')
db_name = os.environ.get('MONGODB_DB', 'myprofessor')
client = MongoClient(uri, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)
db = client[db_name]

# Find and kill the stuck job
for job in db.byo_jobs.find({"state": {"$nin": ["complete", "failed"]}}):
    jid = job["job_id"][:12]
    print(f"Found active job: {jid} state={job.get('state')} resource={job.get('resource_id', '')[:12]}")
    db.byo_jobs.update_one(
        {"_id": job["_id"]},
        {"$set": {"state": "failed", "error": "Killed - document too large for MongoDB"}},
    )
    print(f"  -> Killed {jid}")

print("Done")
