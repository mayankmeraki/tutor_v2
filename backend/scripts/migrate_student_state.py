#!/usr/bin/env python3
"""Migrate student notes from old collections to new structure.

Old: concept_states (one doc per student+course) + student_note_index
New: student_concept_mastery (one doc per student) + student_concept_mastery_vectors

Changes:
- Merges per-course docs into one per-student doc
- Extracts _profile notes into global profile field
- Adds courseId metadata to concept notes
- Renames vector index collection

Usage:
    python -m scripts.migrate_student_state --dry-run
    python -m scripts.migrate_student_state
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

import certifi
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("migrate")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    client = AsyncIOMotorClient(os.environ["MONGODB_URI"], tlsCAFile=certifi.where())
    db = client.tutor_v2

    old_col = db["concept_states"]
    old_idx = db["student_note_index"]
    new_col = db["student_concept_mastery"]
    new_idx = db["student_concept_mastery_vectors"]

    # Count old docs
    old_count = await old_col.count_documents({})
    log.info("Found %d old concept_states documents", old_count)

    if old_count == 0:
        log.info("Nothing to migrate")
        client.close()
        return

    # Group by email
    students = {}
    async for doc in old_col.find({}):
        email = doc.get("userEmail", "").lower()
        if not email:
            continue
        if email not in students:
            students[email] = {"profile": None, "notes": []}

        course_id = doc.get("courseId")
        for note in doc.get("notes", []):
            tags = note.get("tags", [])
            primary = tags[0] if tags else "_uncategorized"

            if primary == "_profile":
                # Global profile — take the most recent one
                students[email]["profile"] = {
                    "text": note.get("text", ""),
                    "updatedAt": note.get("at", datetime.now(timezone.utc).isoformat()),
                }
            else:
                # Add courseId metadata
                new_note = {
                    "text": note.get("text", ""),
                    "tags": tags,
                    "courseId": course_id,
                    "sessionId": note.get("sessionId", ""),
                    "at": note.get("at", ""),
                }
                if note.get("lesson"):
                    new_note["lesson"] = note["lesson"]
                students[email]["notes"].append(new_note)

    log.info("Grouped into %d students", len(students))

    if args.dry_run:
        for email, data in students.items():
            log.info("  %s: profile=%s, %d concept notes",
                     email, "yes" if data["profile"] else "no", len(data["notes"]))
        log.info("Dry run — no data written")
        client.close()
        return

    # Write new docs
    migrated = 0
    for email, data in students.items():
        safe_email = email.replace(".", "_dot_").replace("@", "_at_")
        doc_id = f"mastery_{safe_email}"

        new_doc = {
            "_id": doc_id,
            "userEmail": email,
            "profile": data["profile"],
            "notes": data["notes"],
            "lastUpdated": datetime.now(timezone.utc).isoformat(),
        }

        await new_col.replace_one({"_id": doc_id}, new_doc, upsert=True)
        migrated += 1

    log.info("Migrated %d students to student_concept_mastery", migrated)

    # Migrate vector index
    vec_count = await old_idx.count_documents({})
    if vec_count > 0:
        log.info("Migrating %d vector index entries...", vec_count)
        async for vdoc in old_idx.find({}):
            await new_idx.replace_one({"_id": vdoc["_id"]}, vdoc, upsert=True)
        log.info("Vector index migrated to student_concept_mastery_vectors")

    log.info("Migration complete!")
    log.info("Old collections (concept_states, student_note_index) left intact.")
    log.info("Verify, then drop manually: db.concept_states.drop(); db.student_note_index.drop()")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
