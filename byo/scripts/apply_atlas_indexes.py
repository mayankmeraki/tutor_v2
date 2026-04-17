"""Apply Atlas Search / Vector Search index definitions for BYO collections.

Reads `byo/processing/_atlas_indexes.json` and creates (or updates) the
indexes via the Atlas Admin API. If the required Atlas credentials are not
set in the environment, the script falls back to printing the JSON plus
manual-apply instructions — it does NOT crash.

Entry point:
    python -m byo.scripts.apply_atlas_indexes
    python -m byo.scripts.apply_atlas_indexes --print-only
    python -m byo.scripts.apply_atlas_indexes --database capacity

Required env for API mode:
    ATLAS_PUBLIC_KEY
    ATLAS_PRIVATE_KEY
    ATLAS_PROJECT_ID         (the groupId)
    ATLAS_CLUSTER_NAME
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

log = logging.getLogger("byo.apply_atlas_indexes")

INDEX_FILE = Path(__file__).parent.parent / "processing" / "_atlas_indexes.json"
ATLAS_API_BASE = "https://cloud.mongodb.com/api/atlas/v2"
# Search indexes live under the Atlas v2 "search" controller.
ATLAS_SEARCH_HEADER = "application/vnd.atlas.2024-05-30+json"


def _load_index_file() -> dict[str, Any]:
    if not INDEX_FILE.exists():
        raise FileNotFoundError(f"Atlas index definitions not found: {INDEX_FILE}")
    return json.loads(INDEX_FILE.read_text())


def _print_manual_instructions(indexes: dict[str, Any], database: str) -> None:
    """Fallback path — print the JSON + Atlas UI instructions."""
    print("=" * 72)
    print("Atlas credentials not set. Falling back to manual-apply instructions.")
    print("=" * 72)
    print()
    print("To apply these indexes via the Atlas UI:")
    print("  1. Open https://cloud.mongodb.com and pick your project + cluster.")
    print("  2. Go to: Atlas Search -> Create Search Index -> JSON Editor.")
    print(f"  3. Select database '{database}' and the indicated collection.")
    print("  4. Paste the JSON under the 'definition' key (and set the index")
    print("     name to the key shown below — e.g. 'byo_segments_vector').")
    print("  5. For vectorSearch indexes, pick 'Vector Search' as the type;")
    print("     for 'search' type, pick 'Atlas Search'.")
    print()
    for name, spec in indexes.items():
        print("-" * 72)
        print(f"Index name:        {name}")
        print(f"Type:              {spec.get('type')}")
        print(f"Database:          {spec.get('database', database)}")
        print(f"Collection:        {spec.get('collectionName')}")
        print("Definition:")
        print(json.dumps(spec.get("definition", {}), indent=2))
    print("-" * 72)
    print()
    print("To apply via the API later, set:")
    print("  ATLAS_PUBLIC_KEY, ATLAS_PRIVATE_KEY, ATLAS_PROJECT_ID, ATLAS_CLUSTER_NAME")
    print("and re-run: python -m byo.scripts.apply_atlas_indexes")


async def _list_existing(
    client, project_id: str, cluster: str, database: str, collection: str
) -> list[dict[str, Any]]:
    url = (
        f"{ATLAS_API_BASE}/groups/{project_id}/clusters/{cluster}"
        f"/search/indexes/{database}/{collection}"
    )
    resp = await client.get(url, headers={"Accept": ATLAS_SEARCH_HEADER})
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    data = resp.json()
    # v2 may return a list directly or a paginated envelope.
    if isinstance(data, list):
        return data
    return data.get("results", [])


async def _create_index(
    client, project_id: str, cluster: str, spec: dict[str, Any], name: str, database: str
) -> dict[str, Any]:
    url = (
        f"{ATLAS_API_BASE}/groups/{project_id}/clusters/{cluster}/search/indexes"
    )
    body = {
        "collectionName": spec["collectionName"],
        "database": spec.get("database", database),
        "name": name,
        "type": spec["type"],
        "definition": spec["definition"],
    }
    resp = await client.post(
        url,
        headers={
            "Accept": ATLAS_SEARCH_HEADER,
            "Content-Type": ATLAS_SEARCH_HEADER,
        },
        json=body,
    )
    if resp.status_code >= 400:
        raise RuntimeError(
            f"Atlas create failed ({resp.status_code}) for {name}: {resp.text[:400]}"
        )
    return resp.json()


async def _update_index(
    client, project_id: str, cluster: str, index_id: str, spec: dict[str, Any]
) -> dict[str, Any]:
    url = (
        f"{ATLAS_API_BASE}/groups/{project_id}/clusters/{cluster}"
        f"/search/indexes/{index_id}"
    )
    body = {"definition": spec["definition"]}
    resp = await client.patch(
        url,
        headers={
            "Accept": ATLAS_SEARCH_HEADER,
            "Content-Type": ATLAS_SEARCH_HEADER,
        },
        json=body,
    )
    if resp.status_code >= 400:
        raise RuntimeError(
            f"Atlas update failed ({resp.status_code}): {resp.text[:400]}"
        )
    return resp.json()


async def _apply_via_api(indexes: dict[str, Any], database_override: str | None) -> int:
    """Apply every index defined in the JSON. Returns exit code."""
    try:
        import httpx
    except ImportError:
        log.error("httpx is required for --apply. `pip install httpx`")
        return 2

    pub = os.environ["ATLAS_PUBLIC_KEY"]
    priv = os.environ["ATLAS_PRIVATE_KEY"]
    project_id = os.environ["ATLAS_PROJECT_ID"]
    cluster = os.environ["ATLAS_CLUSTER_NAME"]

    auth = httpx.DigestAuth(pub, priv)
    errors = 0
    async with httpx.AsyncClient(auth=auth, timeout=60.0) as client:
        for name, spec in indexes.items():
            database = database_override or spec.get("database") or "capacity"
            collection = spec["collectionName"]
            log.info(
                "Processing %s on %s.%s (type=%s)",
                name, database, collection, spec.get("type"),
            )
            try:
                existing = await _list_existing(
                    client, project_id, cluster, database, collection
                )
                match = next((e for e in existing if e.get("name") == name), None)
                if match:
                    idx_id = match.get("indexID") or match.get("id")
                    log.info("  -> updating existing index %s (%s)", name, idx_id)
                    await _update_index(client, project_id, cluster, idx_id, spec)
                else:
                    log.info("  -> creating new index %s", name)
                    await _create_index(
                        client, project_id, cluster, spec, name, database
                    )
            except Exception as e:
                errors += 1
                log.error("  !! failed on %s: %s", name, e)

    if errors:
        log.error("Completed with %d error(s)", errors)
        return 1
    log.info("All indexes applied successfully.")
    return 0


async def main_async(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply BYO Atlas index definitions.")
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print the index JSON + manual instructions (no API calls).",
    )
    parser.add_argument(
        "--database",
        default=None,
        help="Override the database name (defaults to value in _atlas_indexes.json).",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    indexes = _load_index_file()
    database = args.database or next(
        (v.get("database") for v in indexes.values() if v.get("database")),
        "capacity",
    )

    required = ("ATLAS_PUBLIC_KEY", "ATLAS_PRIVATE_KEY", "ATLAS_PROJECT_ID", "ATLAS_CLUSTER_NAME")
    missing = [k for k in required if not os.environ.get(k)]

    if args.print_only or missing:
        if missing and not args.print_only:
            log.warning("Missing Atlas env vars: %s", ", ".join(missing))
        _print_manual_instructions(indexes, database)
        return 0

    return await _apply_via_api(indexes, args.database)


def main() -> None:
    sys.exit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
