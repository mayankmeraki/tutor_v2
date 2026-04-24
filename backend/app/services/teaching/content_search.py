"""Teaching content search — finds the best matching teaching plan for a given query.

Uses a 3-tier strategy:
  1. Exact slug match
  2. MongoDB text search (title/slug/topic fields)
  3. Keyword alias table (maps common terms to slugs)

All tiers are fast (no external API calls) — suitable for synchronous use in the pipeline.
"""

import logging
import re

log = logging.getLogger(__name__)

# ── Alias table: maps common search terms → teaching plan slugs ──
# This catches queries like "teach me DP", "explain hash maps", "caching strategies"
_ALIASES = {
    # DSA topics
    "dp": "dynamic_programming", "dynamic programming": "dynamic_programming",
    "array": "arrays_hashing", "arrays": "arrays_hashing", "hashing": "arrays_hashing",
    "hash map": "hash_map", "hashmap": "hash_map", "dictionary": "hash_map",
    "two pointer": "two_pointers", "two pointers": "two_pointers",
    "sliding window": "sliding_window", "window": "sliding_window",
    "stack": "stack", "queue": "stack",
    "binary search": "binary_search", "bisect": "binary_search",
    "linked list": "linked_list", "linkedlist": "linked_list",
    "tree": "trees", "trees": "trees", "bst": "trees", "binary tree": "trees",
    "graph": "graphs", "graphs": "graphs", "dfs": "dfs", "bfs": "bfs",
    "backtracking": "backtracking", "recursion": "backtracking",
    "heap": "heap", "priority queue": "heap", "heapq": "heap",
    "greedy": "greedy", "intervals": "intervals", "merge intervals": "intervals",
    "sorting": "sorting", "sort": "sorting",
    "string": "string", "strings": "string",
    "matrix": "matrix", "grid": "matrix",
    "math": "math", "geometry": "math",
    "bit": "bit_manipulation", "bits": "bit_manipulation", "bitwise": "bit_manipulation",
    "trie": "trie", "prefix tree": "trie",
    "union find": "union_find", "disjoint set": "union_find",
    "topological sort": "topological_sort", "topological": "topological_sort",

    # SD topics
    "redis": "redis", "cache": "caching", "caching": "caching", "memcached": "caching",
    "kafka": "kafka", "message queue": "message_queues", "rabbitmq": "message_queues",
    "sqs": "message_queues", "pub sub": "message_queues", "pubsub": "message_queues",
    "sharding": "sharding", "partition": "sharding", "shard": "sharding",
    "consistent hashing": "consistent_hashing", "hash ring": "consistent_hashing",
    "cap theorem": "cap_theorem", "cap": "cap_theorem", "consistency": "cap_theorem",
    "database index": "database_indexing", "indexing": "database_indexing", "b-tree": "database_indexing",
    "sql": "sql_vs_nosql", "nosql": "sql_vs_nosql", "database": "sql_vs_nosql",
    "api design": "api_design", "rest": "api_design", "grpc": "api_design", "api": "api_design",
    "networking": "networking", "tcp": "networking", "dns": "networking", "http": "networking",
    "data modeling": "data_modeling", "schema design": "data_modeling", "normalization": "data_modeling",
    "elasticsearch": "elasticsearch", "elastic": "elasticsearch", "search": "elasticsearch",
    "numbers": "numbers_to_know", "back of envelope": "numbers_to_know", "estimation": "numbers_to_know",
    "load balancing": "load-balancing", "load balancer": "load-balancing",
    "replication": "replication", "replica": "replication",
    "cdn": "caching", "edge cache": "caching",

    # LLD topics
    "oop": "oop-principles", "object oriented": "oop-principles", "encapsulation": "oop-principles",
    "solid": "solid-principles", "single responsibility": "solid-principles",
    "design patterns": "design-patterns-creational", "factory": "design-patterns-creational",
    "observer": "design-patterns-behavioral", "strategy": "design-patterns-behavioral",
    "adapter": "design-patterns-structural", "decorator": "design-patterns-structural",
    "uml": "uml-class-diagrams", "class diagram": "uml-class-diagrams",
}


def find_teaching_plan(db, slug: str | None, intent: str | None, slog=None) -> dict | None:
    """Find the best matching teaching plan using 3-tier search.

    Args:
        db: PyMongo database (synchronous)
        slug: Topic slug from session context (e.g., "arrays_hashing")
        intent: Student's free-text intent (e.g., "teach me dynamic programming")
        slog: Optional session logger

    Returns:
        Teaching plan document (without _id) or None
    """
    col = db["teaching_plans"]

    # ── Tier 1: Exact slug match ──
    if slug:
        for variant in [slug, slug.replace("_", "-"), slug.replace("-", "_")]:
            plan = col.find_one({"slug": variant}, {"_id": 0})
            if plan:
                if slog: slog.info("[ContentSearch] Tier 1 exact match: %s", variant)
                return plan

    # ── Tier 2: Alias table lookup from intent ──
    if intent:
        _clean = re.sub(r'^(teach|explain|learn|study|help|show|tell|what is|how does)\s+(me\s+)?(about\s+)?', '', intent.lower()).strip()
        _clean = re.sub(r'\s+(work|works|pattern|strategy|strategies|algorithm|concept)s?$', '', _clean).strip()

        # Direct alias match
        if _clean in _ALIASES:
            plan = col.find_one({"slug": _ALIASES[_clean]}, {"_id": 0})
            if plan:
                if slog: slog.info("[ContentSearch] Tier 2 alias: '%s' → %s", _clean, _ALIASES[_clean])
                return plan

        # Partial alias match (longest match wins)
        best_match = None
        best_len = 0
        for alias, target_slug in _ALIASES.items():
            if alias in _clean and len(alias) > best_len:
                best_match = target_slug
                best_len = len(alias)
        if best_match:
            plan = col.find_one({"slug": best_match}, {"_id": 0})
            if plan:
                if slog: slog.info("[ContentSearch] Tier 2 partial alias: '%s' → %s", _clean, best_match)
                return plan

    # ── Tier 3: MongoDB text search ──
    if intent and len(intent) > 3:
        _query = re.sub(r'^(teach|explain|learn|study|help|show|tell)\s+(me\s+)?(about\s+)?', '', intent.lower()).strip()
        if _query:
            try:
                plan = col.find_one(
                    {"$text": {"$search": _query}},
                    {"_id": 0, "score": {"$meta": "textScore"}},
                )
                if plan:
                    if slog: slog.info("[ContentSearch] Tier 3 text search: '%s' → %s", _query, plan.get("slug"))
                    return plan
            except Exception:
                pass

            # Tier 3b: regex on title
            words = [w for w in _query.split() if len(w) >= 3]
            for word in words:
                plan = col.find_one({"title": {"$regex": word, "$options": "i"}}, {"_id": 0})
                if plan:
                    if slog: slog.info("[ContentSearch] Tier 3b regex: '%s' → %s", word, plan.get("slug"))
                    return plan

    return None
