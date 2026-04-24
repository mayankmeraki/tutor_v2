"""Seed SD & LLD concept data into MongoDB ui_config collection.

Usage:
    python seed_sd_concepts.py

Reads MONGODB_URI from .env (same dir) and upserts into tutor_v2.ui_config.
"""

import os
import certifi
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

MONGODB_URI = os.environ["MONGODB_URI"]

SD_CONCEPTS = [
    {
        "section": "Core Concepts",
        "items": [
            {"name": "Networking Essentials", "slug": "networking", "icon": "\U0001f310", "desc": "TCP/UDP, DNS, HTTP, load balancing fundamentals"},
            {"name": "API Design", "slug": "api-design", "icon": "\U0001f50c", "desc": "REST vs gRPC, pagination, rate limiting, versioning"},
            {"name": "Data Modeling", "slug": "data-modeling", "icon": "\U0001f4d0", "desc": "Schema design, normalization, denormalization trade-offs"},
            {"name": "Database Indexing", "slug": "db-indexing", "icon": "\U0001f4c7", "desc": "B-trees, hash indexes, composite indexes, query planning"},
            {"name": "Caching", "slug": "caching", "icon": "\u26a1", "desc": "Cache-aside, write-through, TTL, eviction policies"},
            {"name": "Sharding", "slug": "sharding", "icon": "\U0001f500", "desc": "Range vs hash sharding, rebalancing, hot spots"},
            {"name": "Consistent Hashing", "slug": "consistent-hashing", "icon": "\U0001f3af", "desc": "Virtual nodes, ring topology, minimal redistribution"},
            {"name": "CAP Theorem", "slug": "cap-theorem", "icon": "\u2696\ufe0f", "desc": "Consistency vs availability, partition tolerance trade-offs"},
            {"name": "Numbers to Know", "slug": "numbers-to-know", "icon": "\U0001f522", "desc": "Latency, throughput, storage estimates for back-of-envelope"},
        ],
    },
    {
        "section": "Patterns",
        "items": [
            {"name": "Real-time Updates", "slug": "realtime-updates", "icon": "\U0001f4e1", "desc": "WebSockets, SSE, long polling, pub/sub"},
            {"name": "Dealing with Contention", "slug": "contention", "icon": "\U0001f512", "desc": "Optimistic/pessimistic locking, CAS, queuing"},
            {"name": "Multi-step Processes", "slug": "sagas", "icon": "\U0001f517", "desc": "Sagas, compensating transactions, idempotency"},
            {"name": "Scaling Reads", "slug": "scaling-reads", "icon": "\U0001f4d6", "desc": "Read replicas, caching layers, CDN, denormalization"},
            {"name": "Scaling Writes", "slug": "scaling-writes", "icon": "\u270d\ufe0f", "desc": "Sharding, write-ahead log, batching, async writes"},
            {"name": "Handling Large Blobs", "slug": "large-blobs", "icon": "\U0001f4e6", "desc": "Chunked upload, S3, CDN, resumable transfers"},
            {"name": "Long Running Tasks", "slug": "long-tasks", "icon": "\u23f3", "desc": "Job queues, workers, progress tracking, retries"},
        ],
    },
    {
        "section": "Key Technologies",
        "items": [
            {"name": "Redis", "slug": "redis", "icon": "\U0001f534", "desc": "In-memory cache, pub/sub, sorted sets, rate limiting"},
            {"name": "Elasticsearch", "slug": "elasticsearch", "icon": "\U0001f50d", "desc": "Full-text search, inverted index, aggregations"},
            {"name": "Kafka", "slug": "kafka", "icon": "\U0001f4e8", "desc": "Event streaming, partitions, consumer groups, exactly-once"},
            {"name": "API Gateway", "slug": "api-gateway", "icon": "\U0001f6aa", "desc": "Routing, auth, rate limiting, request transformation"},
            {"name": "Cassandra", "slug": "cassandra", "icon": "\U0001f48e", "desc": "Wide-column, eventual consistency, high write throughput"},
            {"name": "DynamoDB", "slug": "dynamodb", "icon": "\u26a1", "desc": "Serverless, single-digit ms latency, partition key design"},
            {"name": "PostgreSQL", "slug": "postgresql", "icon": "\U0001f418", "desc": "ACID, JSONB, extensions, read replicas"},
            {"name": "ZooKeeper", "slug": "zookeeper", "icon": "\U0001f981", "desc": "Distributed coordination, leader election, config mgmt"},
        ],
    },
]

LLD_CONCEPTS = [
    {
        "section": "Core Principles",
        "items": [
            {"name": "OOP Principles", "slug": "oop-principles", "icon": "\U0001f9f1", "desc": "Encapsulation, inheritance, polymorphism, abstraction"},
            {"name": "SOLID Principles", "slug": "solid-principles", "icon": "\U0001f3d7\ufe0f", "desc": "Single Responsibility, Open/Closed, Liskov, ISP, DIP"},
            {"name": "UML Class Diagrams", "slug": "uml-class-diagrams", "icon": "\U0001f4ca", "desc": "Classes, relationships, associations, composition"},
            {"name": "LLD Framework", "slug": "lld-framework", "icon": "\U0001f5fa\ufe0f", "desc": "Requirements \u2192 Entities \u2192 Relationships \u2192 Patterns \u2192 Code"},
        ],
    },
    {
        "section": "Design Patterns",
        "items": [
            {"name": "Creational Patterns", "slug": "design-patterns-creational", "icon": "\U0001f3ed", "desc": "Factory, Abstract Factory, Builder, Singleton, Prototype"},
            {"name": "Structural Patterns", "slug": "design-patterns-structural", "icon": "\U0001f50c", "desc": "Adapter, Bridge, Composite, Decorator, Facade, Proxy"},
            {"name": "Behavioral Patterns", "slug": "design-patterns-behavioral", "icon": "\U0001f3ad", "desc": "Observer, Strategy, Command, State, Template Method"},
        ],
    },
]


def main():
    client = MongoClient(
        MONGODB_URI,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
    )

    # Verify connectivity
    client.admin.command("ping")
    print("Connected to MongoDB")

    db = client[os.environ.get("MONGODB_DB", "capacity")]
    coll = db["ui_config"]

    # Upsert sd_concepts
    result_sd = coll.update_one(
        {"key": "sd_concepts"},
        {"$set": {"key": "sd_concepts", "sections": SD_CONCEPTS}},
        upsert=True,
    )
    action_sd = "inserted" if result_sd.upserted_id else "updated"
    print(f"sd_concepts: {action_sd}")

    # Upsert lld_concepts
    result_lld = coll.update_one(
        {"key": "lld_concepts"},
        {"$set": {"key": "lld_concepts", "sections": LLD_CONCEPTS}},
        upsert=True,
    )
    action_lld = "inserted" if result_lld.upserted_id else "updated"
    print(f"lld_concepts: {action_lld}")

    # Create index on key field
    coll.create_index("key", unique=True)
    print("Index on 'key' ensured")

    # ── Verify: read back and print summary ──
    print("\n── Verification ──")
    for key in ("sd_concepts", "lld_concepts"):
        doc = coll.find_one({"key": key}, {"_id": 0})
        if not doc:
            print(f"  {key}: NOT FOUND")
            continue
        sections = doc.get("sections", [])
        total_items = sum(len(s.get("items", [])) for s in sections)
        section_names = [s["section"] for s in sections]
        print(f"  {key}: {len(sections)} sections, {total_items} items")
        for s in sections:
            items = s.get("items", [])
            print(f"    - {s['section']}: {len(items)} items ({', '.join(i['slug'] for i in items[:3])}{'...' if len(items) > 3 else ''})")

    client.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
