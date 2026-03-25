#!/usr/bin/env python3
"""One-time script: enrich course sections with LLM-generated teaching briefs.

Reads all sections from MongoDB `capacity.sections`, sends each to Haiku
via direct Anthropic API, writes structured teaching data to `capacity.enriched_sections`.

Usage:
    # Preview what would be processed
    python -m scripts.enrich_sections --dry-run

    # Process all sections
    python -m scripts.enrich_sections

    # Process a single lesson
    python -m scripts.enrich_sections --lesson-id 6

    # Force re-process (overwrite existing enrichments)
    python -m scripts.enrich_sections --force

Requires:
    ANTHROPIC_API_KEY  — direct Claude API key (not OpenRouter)
    MONGODB_URI        — MongoDB connection string
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time

# Add parent dir to path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import anthropic
import certifi
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("enrich")

HAIKU_MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1024

ENRICHMENT_PROMPT = """\
You are a curriculum designer. Extract structured teaching data from this lecture section.

Section title: {title}
Transcript: {transcript}
Key points from course: {key_points}
Concepts covered: {concepts}
Formulas mentioned: {formulas}

Return ONLY valid JSON (no markdown fences) with these fields:
{{
  "teaching_summary": "2-3 sentence summary a tutor can use to teach this topic without reading the full transcript. Focus on the core idea and why it matters.",
  "key_pedagogical_points": ["4-6 bullet points covering the essential teaching content — what a student must understand"],
  "notable_examples": ["Professor's analogies, real-world examples, or memorable explanations — quote or closely paraphrase. Empty array if none."],
  "professor_framing": "1-2 sentences on how the professor introduces/motivates this topic — the hook that makes it interesting"
}}"""


async def main():
    parser = argparse.ArgumentParser(description="Enrich course sections with LLM teaching briefs")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--lesson-id", type=int, help="Process only this lesson")
    parser.add_argument("--force", action="store_true", help="Re-process existing enrichments")
    args = parser.parse_args()

    # Connect to MongoDB
    mongo_uri = os.environ.get("MONGODB_URI")
    if not mongo_uri:
        log.error("MONGODB_URI not set")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = AsyncIOMotorClient(mongo_uri, tlsCAFile=certifi.where())
    db = client["capacity"]
    sections_col = db["sections"]
    enriched_col = db["enriched_sections"]

    # Ensure index
    await enriched_col.create_index(
        [("lesson_id", 1), ("section_index", 1)],
        unique=True,
    )

    # Build query
    query = {}
    if args.lesson_id:
        query["lesson_id"] = args.lesson_id

    cursor = sections_col.find(query).sort([("lesson_id", 1), ("index", 1)])
    sections = await cursor.to_list(length=500)

    log.info("Found %d sections to process", len(sections))

    # Anthropic client (sync — simpler for batch work)
    claude = anthropic.Anthropic(api_key=api_key)

    stats = {"processed": 0, "skipped": 0, "errors": 0}

    for sec in sections:
        lesson_id = sec.get("lesson_id")
        section_index = sec.get("index")
        title = sec.get("title", f"Section {section_index}")

        # Check if already enriched
        if not args.force:
            existing = await enriched_col.find_one(
                {"lesson_id": lesson_id, "section_index": section_index},
                {"_id": 1},
            )
            if existing:
                log.debug("Skipping %d:%d (already enriched)", lesson_id, section_index)
                stats["skipped"] += 1
                continue

        # Build transcript
        segments = sec.get("segments")
        transcript_text = sec.get("transcript", "")
        if segments and isinstance(segments, list):
            transcript = " ".join(
                s.get("text", s) if isinstance(s, dict) else str(s)
                for s in segments
            )
        elif transcript_text:
            transcript = transcript_text
        else:
            log.warning("No transcript for %d:%d — skipping", lesson_id, section_index)
            stats["skipped"] += 1
            continue

        # Truncate long transcripts
        if len(transcript) > 6000:
            transcript = transcript[:6000] + "..."

        key_points = sec.get("key_points", [])
        concepts = sec.get("concepts", [])
        formulas = sec.get("formulas", [])

        prompt = ENRICHMENT_PROMPT.format(
            title=title,
            transcript=transcript,
            key_points=", ".join(key_points) if key_points else "None listed",
            concepts=", ".join(concepts) if concepts else "None listed",
            formulas=", ".join(str(f) for f in formulas) if formulas else "None listed",
        )

        if args.dry_run:
            log.info("[DRY RUN] Would process %d:%d — %s (%d chars transcript)",
                     lesson_id, section_index, title, len(transcript))
            stats["processed"] += 1
            continue

        # Call Haiku
        try:
            log.info("Processing %d:%d — %s", lesson_id, section_index, title)
            response = claude.messages.create(
                model=HAIKU_MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )

            text = response.content[0].text.strip()
            # Strip markdown fences if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            data = json.loads(text)

            # Validate
            if not isinstance(data.get("teaching_summary"), str):
                raise ValueError("Missing teaching_summary")
            if not isinstance(data.get("key_pedagogical_points"), list):
                raise ValueError("Missing key_pedagogical_points")

            # Upsert into enriched_sections
            doc = {
                "lesson_id": lesson_id,
                "section_index": section_index,
                "title": title,
                "start_seconds": sec.get("start_seconds"),
                "end_seconds": sec.get("end_seconds"),
                "teaching_summary": data["teaching_summary"],
                "key_pedagogical_points": data["key_pedagogical_points"],
                "concepts": concepts,
                "formulas": [str(f) for f in formulas],
                "notable_examples": data.get("notable_examples", []),
                "professor_framing": data.get("professor_framing", ""),
                "source_section_id": str(sec.get("_id", "")),
                "enriched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "model_used": HAIKU_MODEL,
            }

            await enriched_col.update_one(
                {"lesson_id": lesson_id, "section_index": section_index},
                {"$set": doc},
                upsert=True,
            )

            stats["processed"] += 1
            log.info("  ✓ Enriched %d:%d — %d points, %d examples",
                     lesson_id, section_index,
                     len(data["key_pedagogical_points"]),
                     len(data.get("notable_examples", [])))

            # Rate limit — be gentle
            await asyncio.sleep(0.3)

        except json.JSONDecodeError as e:
            log.error("  ✗ JSON parse failed for %d:%d: %s — raw: %s",
                      lesson_id, section_index, e, text[:200])
            stats["errors"] += 1
        except Exception as e:
            log.error("  ✗ Failed %d:%d: %s", lesson_id, section_index, e)
            stats["errors"] += 1

    log.info("Done! Processed: %d, Skipped: %d, Errors: %d",
             stats["processed"], stats["skipped"], stats["errors"])

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
