#!/usr/bin/env python3
"""Seed DSA and System Design teaching plans into MongoDB.

Usage:
    python -m byo.scripts.seed_teaching_plans
    python -m byo.scripts.seed_teaching_plans --drop   # drop existing before seeding
    python -m byo.scripts.seed_teaching_plans --uri "mongodb+srv://..."
"""

import argparse
import os
import sys

def main():
    parser = argparse.ArgumentParser(description="Seed teaching plans into MongoDB")
    parser.add_argument("--drop", action="store_true", help="Drop existing collection before seeding")
    parser.add_argument("--uri", type=str, default=None, help="MongoDB URI override")
    args = parser.parse_args()

    # Load env
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, root)
    sys.path.insert(0, os.path.join(root, "backend"))
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(root, "backend", ".env"), override=False)
    except ImportError:
        pass

    uri = args.uri or os.environ.get("MONGODB_URI", "")
    if not uri:
        print("ERROR: MONGODB_URI not set")
        sys.exit(1)

    import certifi
    from pymongo import MongoClient

    client = MongoClient(uri, tlsCAFile=certifi.where())
    db = client["tutor_v2"]
    collection = db["teaching_plans"]

    if args.drop:
        collection.drop()
        print("Dropped existing teaching_plans collection")

    # Load plans
    from byo.scripts.teaching_plans import DSA_TEACHING_PLANS, SD_TEACHING_PLANS

    docs = []

    # DSA plans
    for slug, plan in DSA_TEACHING_PLANS.items():
        docs.append({
            "slug": slug,
            "type": "dsa",
            **plan,
        })

    # SD plans
    for slug, plan in SD_TEACHING_PLANS.items():
        docs.append({
            "slug": slug,
            "type": "sd",
            **plan,
        })

    if docs:
        collection.insert_many(docs)
        print(f"Inserted {len(docs)} teaching plans ({len(DSA_TEACHING_PLANS)} DSA + {len(SD_TEACHING_PLANS)} SD)")

    # Create indexes
    collection.create_index("slug", unique=True)
    collection.create_index("type")
    print("Indexes created: slug (unique), type")

    print("Done!")


if __name__ == "__main__":
    main()
