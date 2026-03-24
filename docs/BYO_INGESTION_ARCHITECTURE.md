# BYO Material Ingestion Pipeline — Architecture Specification

> **Status**: Backend pipeline 70% complete, Frontend 0%, Vector search 0%, Deletion 0%
> **Last updated**: March 2026
> **Audience**: Principal Engineer / Architecture Review

---

## Table of Contents

1. [What Problem Does This Solve?](#1-what-problem-does-this-solve)
2. [Design Philosophy — SDK, Not a Monolith](#2-design-philosophy--sdk-not-a-monolith)
3. [Honest Critique — Is This Overengineered?](#3-honest-critique--is-this-overengineered)
4. [The Bare-Minimum System (Layer 0)](#4-the-bare-minimum-system-layer-0)
5. [Layered Architecture — How Complexity Grows](#5-layered-architecture--how-complexity-grows)
6. [End-to-End: How Every Query Type Gets Answered](#6-end-to-end-how-every-query-type-gets-answered)
7. [System Architecture](#7-system-architecture)
8. [Source Types & Ingestion Matrix](#8-source-types--ingestion-matrix)
9. [Pipeline Stages (Detailed)](#9-pipeline-stages-detailed)
10. [MongoDB Schema (All Collections)](#10-mongodb-schema-all-collections)
11. [GCS Storage Layout](#11-gcs-storage-layout)
12. [REST API Surface](#12-rest-api-surface)
13. [Material Query Layer (MQL)](#13-material-query-layer-mql)
14. [Vector Search & Embeddings](#14-vector-search--embeddings)
15. [Incremental Update & Merge Strategy](#15-incremental-update--merge-strategy)
16. [Deletion Pipeline (Cascading)](#16-deletion-pipeline-cascading)
17. [Teaching Context — How the Tutor Sees BYO Content](#17-teaching-context--how-the-tutor-sees-byo-content)
18. [Frontend Integration Points](#18-frontend-integration-points)
19. [External Dependencies & Cost Model](#19-external-dependencies--cost-model)
20. [Production Concerns](#20-production-concerns)
21. [Implementation Status & Gaps](#21-implementation-status--gaps)

---

## 1. What Problem Does This Solve?

### The Core Problem

A student has learning materials scattered across formats — lecture PDFs, YouTube recordings, handwritten notes, problem sets, slides. They want an AI tutor that can:

- **Teach** from THEIR materials (not generic internet knowledge)
- **Answer questions** grounded in what their professor actually said
- **Assess** them using the exercises from their actual course
- **Track** what they've learned and what they haven't

The tutor cannot simply dump 200 pages of PDF into its context window. Even if it could, it wouldn't know what to teach first, what depends on what, or what the student already understands.

### What This Service Does

It takes raw student materials (any format) and produces a **structured, queryable, teachable library** that any LLM-based tutor can navigate — the same way a human tutor would navigate a textbook:

1. Look at the table of contents
2. Find the right chapter
3. Read the relevant section
4. Teach it
5. Quiz the student
6. Track mastery

### The End Goal

A student should be able to:
- Upload anything (PDF, video, notes, links)
- Immediately (within minutes) start a teaching session
- Ask ANY type of question — structured ("teach me chapter 3"), ad-hoc ("explain that energy thing"), assessment ("test me on last week's lecture"), conceptual ("why does entropy increase?") — and get answers grounded in their actual materials

---

## 2. Design Philosophy — SDK, Not a Monolith

This system is designed as a **decoupled content intelligence layer** — not tied to any specific tutor implementation.

### The Interface Contract

Any tutor (ours or third-party) integrates via two surfaces:

**Surface 1: REST API** (material management)
```
POST   /collections              → create a library
POST   /collections/{id}/upload  → add material
GET    /collections/{id}/status  → check processing
DELETE /collections/{id}         → cleanup
```

**Surface 2: Tool Calling** (teaching — the MQL)
```python
# Tutor gets these as callable tools:
browse_topics(collection_id) → list of topics
read_chunk(chunk_id)         → full content of a section
search(collection_id, query) → find relevant chunks
get_exercises(topic_id)      → practice problems
get_mastery(collection_id)   → student progress
log_observation(concept, note) → record learning event
```

The tutor doesn't know or care about the pipeline, MongoDB, GCS, or embeddings. It sees a simple library interface: browse, search, read, assess.

### Why This Matters

- **Swap the tutor**: Different tutors (math specialist, language tutor, exam prep) can use the same content library
- **Swap the pipeline**: Replace the chunking strategy, embedding model, or storage without touching the tutor
- **Swap the LLM**: The MQL tools work identically whether the tutor runs GPT, Claude, or a fine-tuned model
- **Test independently**: Pipeline has its own tests; tutor has its own tests; they communicate via a stable interface

---

## 3. Honest Critique — Is This Overengineered?

**Short answer: Yes, for v1. The full spec has 14 MongoDB collections, a 10-stage pipeline, 12 query tools, a concept graph, incremental merge locking, and flow map generation. That's a lot.**

Let's be honest about what the LLM can and cannot do at query time, because that determines what we actually need to pre-compute.

### What the LLM CAN figure out on its own (given chunks)

| Capability | Pre-computed in current design | Actually needed? |
|-----------|-------------------------------|-----------------|
| Identify topics from a list of chunk titles | `topic_index` | **No** — LLM can group chunks by scanning titles |
| Decide teaching order | `flow_map` with chapter sequencing | **No** — LLM can sequence topics itself if it sees the list |
| Extract concepts from content | `concept_graph` with dedup + aliases | **No** — LLM identifies concepts as it reads chunks |
| Rate difficulty | `difficulty_map` | **No** — LLM can assess difficulty from content |
| Create exercises | `exercise_index` | **Partially** — LLM can generate exercises, but extracting EXISTING ones from problem sets is valuable |
| Decide what to teach next | Flow map + mastery state | **Partially** — LLM can decide, but needs stable IDs for progress tracking |

### What the LLM CANNOT do without pre-computation

| Capability | Why pre-computation is essential |
|-----------|--------------------------------|
| **Read the material** | 200 pages won't fit in context. Must chunk first. |
| **Find relevant content** | Must have search (keyword or vector). Can't scan all chunks per query. |
| **Remember across sessions** | Progress must persist. Need stable topic/concept IDs to track mastery. |
| **Handle concurrent uploads** | Pipeline must process materials asynchronously with merge safety. |

### The Real Question

**Can we get 80% of the value with 20% of the complexity?**

Yes. Here's how.

---

## 4. The Bare-Minimum System (Layer 0)

### What It Takes to Start Teaching

The absolute minimum to make "teach me from my uploaded PDF" work:

```
Upload → Extract text → Chunk (fixed-size) → Store chunks → Search + Read
```

**That's it.** 3 MongoDB collections. 3 API tools. 1 pipeline with 3 stages.

### Layer 0 Schema (3 collections)

```
collections:   { id, userId, title, status }
materials:     { id, collectionId, sourceType, title, status, text }
chunks:        { id, materialId, collectionId, index, title, text, summary }
```

### Layer 0 Pipeline (3 stages)

1. **Extract**: PDF → text (PyMuPDF), YouTube → transcript (captions API), Text → normalize
2. **Chunk**: Split into ~1500 char sections at paragraph boundaries (no LLM needed)
3. **Summarize**: LLM writes a 1-line summary per chunk (Haiku, cheap — or skip entirely)

### Layer 0 Tools (3 tools)

```python
list_chunks(collection_id)            → [{id, title, summary}]  # table of contents
read_chunk(chunk_id)                  → full text
search(collection_id, query)          → keyword match across chunks
```

### What Layer 0 Handles

| Student Request | How It Works |
|----------------|-------------|
| "Teach me my course" | Tutor calls `list_chunks()` → sees all sections → teaches sequentially |
| "Explain the energy part" | Tutor calls `search("energy")` → reads matching chunks → teaches |
| "I have a doubt about F=ma" | Tutor calls `search("F=ma")` → reads chunk → clarifies |
| "Give me a practice problem" | Tutor reads relevant chunks → **generates** exercises on the fly |

### What Layer 0 DOESN'T Handle Well

- **"Teach me from topic X"** — no topic grouping, tutor must guess from chunk titles
- **"Test me on past exam papers"** — exercises aren't extracted, tutor can only generate new ones
- **Progress tracking** — no stable topic IDs, so "where did we leave off?" is unreliable
- **Fuzzy search** — "the rotational force thing" won't match chunks about "torque"
- **Visual assets** — no frame extraction, diagrams aren't indexed

### Layer 0 Cost

- Pipeline: ~$0.005 per material (just the summarization LLM call, or $0 if skipped)
- Storage: just text, negligible
- Latency: seconds (no LLM in the chunking path if we use fixed-size)

### Verdict

**Layer 0 is shippable in 3-4 days.** It handles the happy path: student uploads, tutor teaches. The LLM is smart enough to navigate simple chunk lists and synthesize teaching from raw content. This is the MVP.

---

## 5. Layered Architecture — How Complexity Grows

Each layer adds capability. Each layer is optional. Ship Layer 0, validate, then add layers based on what users actually need.

```
┌────────────────────────────────────────────────────────────────┐
│ LAYER 3: Polish                                                │
│ Vector search, visual assets, frame extraction, PPTX/DOCX     │
│ → Fuzzy queries, diagram access, all file types                │
├────────────────────────────────────────────────────────────────┤
│ LAYER 2: Intelligence                                          │
│ Concept graph, exercise extraction, progress tracking          │
│ → Assessment, spaced repetition, mastery-based teaching        │
├────────────────────────────────────────────────────────────────┤
│ LAYER 1: Structure                                             │
│ Topic detection, flow map, classification, quality gate        │
│ → Structured courses, prerequisite ordering, crash courses     │
├────────────────────────────────────────────────────────────────┤
│ LAYER 0: Bare Minimum (MVP)                                    │
│ Extract → Chunk → Store → Search → Read                        │
│ → Ad-hoc teaching, doubt solving, basic structured teaching    │
└────────────────────────────────────────────────────────────────┘
```

### Layer 1: Structure (+1 week)

**Adds**: LLM-based chunking (semantic boundaries instead of fixed-size), material classification, topic detection, flow map generation, quality gate.

**New collections**: `topic_index`, `flow_map`

**New tools**: `browse_topics()`, `browse_topic(topicId)`, `get_flow()`

**What it unlocks**:
- "Teach me my course" → proper chapter/topic sequence
- "Prepare a crash course" → tutor uses flow map to select key topics
- "Skip to dynamics" → tutor finds the dynamics topic group
- Rejects garbage uploads (quality gate)

**Why it's worth it**: The difference between "here are 47 chunks, good luck" and "here are 8 topics organized into 3 chapters" is massive for teaching quality. The tutor makes much better decisions with structure.

### Layer 2: Intelligence (+1 week)

**Adds**: Concept graph (with deduplication + prerequisites), exercise extraction from problem sets, student progress tracking with concept mastery.

**New collections**: `concept_graph`, `exercise_index`, `student_progress`, `difficulty_map`

**New tools**: `find_concept()`, `search_concepts()`, `get_exercises()`, `get_mastery()`, `log_observation()`

**What it unlocks**:
- "Test me on this topic" → real exercises from their actual problem sets (not LLM-generated)
- "What should I study for the exam?" → mastery gaps identified from tracked progress
- Prerequisites enforced → tutor won't teach integration before limits
- "I struggle with friction problems" → concept mastery shows weak areas

**Why it's worth it**: This is what separates "AI that reads your PDF" from "AI tutor that knows your course". Exercise extraction from actual past papers is the killer feature for exam prep.

### Layer 3: Polish (+1 week)

**Adds**: Vector embeddings + semantic search, visual asset index (frame extraction + classification + OCR), image/video file upload support, PPTX/DOCX parsing.

**New collections**: `extracted_frames`, `asset_index` (+ embeddings on `chunks`)

**New tools**: `semantic_search()`, `get_assets()`

**What it unlocks**:
- "Explain that derivation thing" → vector search finds it even without exact keywords
- "Show me the diagram from lecture 3" → frame-level visual asset access
- Upload lecture recordings (MP4) and PowerPoints directly

**Why it's worth it**: Vector search is the biggest quality-of-life improvement for ad-hoc queries. Students don't use precise terminology — they say "the energy conservation thingy" not "first law of thermodynamics".

---

## 6. End-to-End: How Every Query Type Gets Answered

This is the real test. Work backwards from what the student asks to what the system needs.

### Query Type 1: Ad-Hoc Questions

> "Hey, can you explain what the professor meant about entropy in lecture 5?"

```
Layer 0 path:  search("entropy lecture 5") → read matching chunk → teach
Layer 3 path:  semantic_search("entropy concept from lecture 5") → more precise match
```

**Layer 0 is sufficient.** Vector search makes it better but isn't required.

### Query Type 2: Structured Teaching

> "Teach me my course from the beginning"

```
Layer 0 path:  list_chunks() → tutor sequences them by material/index → teaches in order
Layer 1 path:  get_flow() → proper chapter sequence → browse_topic() → read_chunk() → teach
```

**Layer 0 works but is messy.** The tutor gets a flat list and must infer structure. Layer 1's flow map makes this dramatically better.

### Query Type 3: Topic-Based Teaching

> "I want to learn about electromagnetic induction"

```
Layer 0 path:  search("electromagnetic induction") → read matching chunks → teach
Layer 1 path:  browse_topics() → find topic → browse_topic() → teach with full context
```

**Layer 0 works.** Layer 1 provides the topic boundary (where does "induction" start and end?) which helps the tutor give a complete explanation rather than a fragment.

### Query Type 4: Assessment / Exam Prep

> "Test me on past exam papers I uploaded"

```
Layer 0 path:  search("problem" OR "exercise" OR "calculate") → tutor reads chunks → generates questions
Layer 2 path:  get_exercises(difficulty="advanced") → real problems from their actual exam papers
```

**Layer 0 is significantly worse.** It can only generate new problems from content. Layer 2 extracts the actual problems with solutions — much more valuable for exam prep. This is the strongest argument for Layer 2.

### Query Type 5: Doubt Solving

> "I don't understand why kinetic energy is ½mv² and not mv²"

```
Layer 0 path:  search("kinetic energy derivation") → read chunk → explain
Layer 2 path:  find_concept("kinetic_energy") → see definition + prerequisites → deeper explanation
Layer 3 path:  semantic_search("why is kinetic energy one half mv squared") → precise chunk match
```

**Layer 0 works if the material covers this.** The concept graph (Layer 2) helps the tutor identify prerequisites the student might be missing. Vector search (Layer 3) helps if the student's phrasing doesn't match the material's terminology.

### Query Type 6: Crash Course

> "Exam in 2 days, give me a crash course"

```
Layer 0 path:  list_chunks() → tutor picks "important-looking" chunks → compressed teaching
Layer 1 path:  get_flow() → tutor selects key topics → skip details → focus on core
Layer 2 path:  get_mastery() → skip already-known topics → focus on gaps → exercises for weak areas
```

**Layer 0 is bad for this.** Without structure, the tutor doesn't know what's important. Without mastery data, it can't skip what the student already knows. Layer 1+2 together make crash courses actually useful.

### Summary: When Does Each Layer Pay For Itself?

| Layer | Query Types It Dramatically Improves | Worth It? |
|-------|--------------------------------------|-----------|
| **0** (MVP) | Ad-hoc questions, basic doubt solving | **Always** — this is the floor |
| **1** (Structure) | Structured teaching, crash courses, topic navigation | **Yes** — goes from "AI that reads your PDF" to "AI that teaches your course" |
| **2** (Intelligence) | Assessment, exam prep, progress-aware teaching | **Yes if exam prep is a use case** — the killer feature for students |
| **3** (Polish) | Fuzzy queries, visual assets, more file types | **Nice-to-have** — improves quality but not capability |

### Recommended Pitch

> **Ship Layer 0 in week 1** — prove the upload-to-teach loop works.
> **Ship Layer 0+1 in week 2** — this is the real product: structured teaching from student materials.
> **Ship Layer 0+1+2 in week 3** — this is the differentiated product: assessment + mastery tracking from their actual course materials.
> **Layer 3 when needed** — vector search and visual assets are quality improvements, not capability gates.

---

## 7. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (app.js)                            │
│  Collection CRUD UI │ Upload/Drop Zone │ Status Polling │ Session   │
└───────────┬─────────┴────────┬──────────┴───────┬───────┴───────────┘
            │ REST              │ REST              │ SSE
            ▼                  ▼                   ▼
┌───────────────────────────────────────────────────────────────────────┐
│                     FASTAPI BACKEND (main.py)                        │
│                                                                       │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────────────┐ │
│  │ Ingestion   │  │ Chat Route   │  │ Signed URL / Resource Route  │ │
│  │ Routes      │  │ (BYO branch) │  │ (raw material access)        │ │
│  └──────┬──────┘  └──────┬───────┘  └──────────────────────────────┘ │
│         │                │                                            │
│  ┌──────▼──────┐  ┌──────▼───────────────┐                          │
│  │ Pipeline    │  │ Lean Context Builder  │                          │
│  │ Orchestrator│  │ + MQL Tool Executor   │                          │
│  └──────┬──────┘  └──────────────────────┘                          │
│         │                                                             │
│  ┌──────▼──────────────────────────────────────────────────────────┐ │
│  │            Processing Pipeline (Layer-dependent)                 │ │
│  │  L0: Extract → Chunk → Store                                    │ │
│  │  L1: + Classify → Smart Chunk → Topic Detect → Sequence         │ │
│  │  L2: + Enrich → Exercises → Concept Graph → Progress            │ │
│  │  L3: + Frames → Embed → Visual Assets                           │ │
│  └──────┬──────────────────────────────────────────────────────────┘ │
└─────────┼─────────────────────────────────────────────────────────────┘
          │
    ┌─────▼─────┐  ┌──────────┐  ┌──────────────────┐  ┌────────────┐
    │  MongoDB   │  │   GCS    │  │ ElevenLabs STT / │  │ Anthropic  │
    │            │  │ (blobs)  │  │ YouTube Captions  │  │ Claude     │
    └───────────┘  └──────────┘  └──────────────────┘  └────────────┘
```

### SDK Integration Points

A third-party tutor integrates at two surfaces:

```
┌──────────────────────┐         ┌─────────────────────────┐
│    ANY TUTOR (SDK)    │         │   BYO Content Service    │
│                       │ REST →  │   /collections/*         │
│  1. Manage materials  │─────────│   /materials/*           │
│                       │         │                           │
│  2. Query content     │ Tools → │   MQL tool executor       │
│     (tool calling)    │─────────│   search, read, browse,   │
│                       │         │   exercises, mastery       │
└──────────────────────┘         └─────────────────────────┘

The tutor NEVER touches MongoDB, GCS, or the pipeline.
The tutor sees: browse, search, read, assess.
```

---

## 8. Source Types & Ingestion Matrix

| Source Type | Upload Method | Extraction | Transcription | Status |
|-------------|--------------|------------|---------------|--------|
| **PDF** | Multipart upload (50MB max) | PyMuPDF (text + embedded images) | N/A | **Implemented** |
| **YouTube Video** | URL | yt-dlp metadata | YouTube captions → ElevenLabs STT fallback | **Implemented** |
| **YouTube Playlist** | URL | yt-dlp expansion → individual videos | Per-video | **Implemented** |
| **Text Paste** | JSON body | Normalization + structure detection | N/A | **Implemented** |
| **Text File** (txt, md) | Multipart upload | UTF-8 decode → text pipeline | N/A | **Implemented** |
| **Image** (JPG, PNG) | Multipart upload | Claude Vision OCR + classification | N/A | **Not implemented** |
| **Video File** (MP4, MOV) | Multipart upload → GCS | ffprobe metadata | ElevenLabs STT | **Not implemented** |
| **PPTX** | Multipart upload | python-pptx slide extraction | N/A | **Not implemented** |
| **DOCX** | Multipart upload | python-docx text extraction | N/A | **Not implemented** |

### Transcription Strategy

Current cascade for YouTube videos:
1. **YouTube Captions** (free, fast) — `youtube-transcript-api`
2. **Deepgram Nova-2** (paid fallback) — when captions unavailable

**Proposed change**: Replace Deepgram with **ElevenLabs Speech-to-Text** for all non-YouTube audio:
- Consolidates vendor (we already pay ElevenLabs for TTS)
- Cost-effective for our volume
- Supports direct audio URL or file upload
- Provides word-level timestamps

---

## 9. Pipeline Stages (Detailed)

Each material runs as a background `asyncio.create_task()`. The pipeline is layer-aware — Layer 0 runs stages 0-2 only, higher layers add more stages.

### Stage 0: VALIDATE
Pre-flight checks before any processing.

| Source | Validation |
|--------|-----------|
| YouTube | URL format, extractable via yt-dlp |
| PDF | Not encrypted, >0 pages, text in first 3 pages (>100 chars) |
| Text | Min 50 chars, >50% alphanumeric ratio |
| Image (proposed) | Valid format, min 100x100 px |
| Video file (proposed) | Valid container, <4 hours |

Failure → material status `rejected` with reason.

### Stage 1: EXTRACT
Get raw content from source.

| Source | Extractor | Output |
|--------|-----------|--------|
| YouTube | `yt-dlp` metadata | Title, duration, thumbnail, description |
| YouTube Playlist | `yt-dlp` flat expand | List of video URLs → child materials |
| PDF | `PyMuPDF` | Per-page text + embedded images → GCS |
| Text | `normalize_text()` | Cleaned text with structure hints |

### Stage 2: TRANSCRIBE (audio/video only)
Speech → timestamped text segments.

```python
@dataclass
class Segment:
    text: str
    start: float   # seconds
    end: float
    speaker: int    # diarization
    confidence: float
```

YouTube: Captions API → ElevenLabs STT fallback.
Video file (proposed): ElevenLabs STT direct.

Stored in MongoDB `transcripts` with GCS backup.

---

**Stages below are Layer 1+ (not needed for MVP)**

### Stage 3: FRAME EXTRACT (Layer 3, video only)
Extract and classify visual content:
1. ffmpeg keyframes (~1 per 5-10 seconds)
2. Claude Vision classifies: `board | equation | diagram | slide | chart | talking_head | transition`
3. Claude Vision OCR on educational frames
4. Upload to GCS, metadata in `extracted_frames`

### Stage 4: CLASSIFY (Layer 1+)
LLM (Haiku) detects material type and subject:

```python
@dataclass
class Classification:
    type: str           # lecture | assignment | exercise_set | reference | notes | mixed
    subjects: list[str] # ["classical mechanics", "kinematics"]
    difficulty: str     # beginner | intermediate | advanced
    is_structured: bool
    has_exercises: bool
    language: str
    confidence: float   # 0.0 - 1.0
    educational_quality: str  # high | medium | low | non_educational
```

### Stage 4b: QUALITY GATE (Layer 1+)
Reject: confidence < 0.4, text < 200 chars, `non_educational`, video > 4 hours.

### Stage 5: CHUNK
**Layer 0**: Fixed-size paragraph-boundary splitting (~1500 chars). No LLM. Instant.

**Layer 1+**: LLM-based semantic chunking:

| Material Type | Strategy | Target |
|--------------|----------|--------|
| Video transcript | LLM detects topic boundaries | 3-7 min per chunk |
| Assignment | LLM splits into individual problems | 1 problem per chunk |
| Structured text | LLM follows heading hierarchy | 300-3000 chars |
| Unstructured | Paragraph-boundary fallback | ~1500 chars |

### Stage 6: ENRICH (Layer 1+, per-chunk, parallelized)
LLM (Haiku) extracts per-chunk:
- Summary (2-3 sentences)
- Key points (3-6)
- Concepts with definitions and roles (introduced / prerequisite / applied)
- Formulas
- Difficulty rating

**Material status → `ready` after this stage.** Teaching can begin.

### Stage 7: EXERCISES (Layer 2, background)
LLM extracts practice problems from exercise-flagged chunks. Distinguishes exercises (student solves) from worked examples (instructor demonstrates). Stores with type, difficulty, concepts, diagram references, and solutions.

### Stage 8: MERGE INDEXES (Layer 1+, incremental, locked)
Most complex stage. Runs per-material with MongoDB-based locking:

1. **Topic merge**: LLM assigns chunks to existing topics or creates new ones
2. **Concept merge**: LLM deduplicates concepts against existing graph
3. **Exercise linking**: Exercises linked to topics via concept overlap
4. **Asset cataloging**: Frames → `asset_index`
5. **Difficulty map** rebuild

Lock mechanism: `index_locks` collection, 5-min timeout, queue in `merge_queue`.

### Stage 9: SEQUENCE (Layer 1+)
LLM generates chapter → topic teaching sequence. Prerequisites before dependents, definitions before applications, easier before harder. Versioned and re-generated on each merge.

---

## 10. MongoDB Schema (All Collections)

### Layer 0 Collections (3)

#### `content_collections`
```json
{
    "collectionId": "uuid",
    "userId": "user-id",
    "title": "Physics 101 — My Notes",
    "status": "processing | partial | ready | error",
    "processingProgress": {
        "totalMaterials": 5,
        "processedMaterials": 3,
        "rejectedMaterials": 1,
        "currentStep": "enriching",
        "errors": []
    },
    "subjects": ["classical mechanics"],
    "stats": { "totalMaterials": 4, "totalChunks": 47, "totalConcepts": 32, "totalExercises": 15, "totalTopics": 8 },
    "createdAt": "datetime",
    "updatedAt": "datetime"
}
```

#### `materials`
```json
{
    "materialId": "uuid",
    "collectionId": "uuid",
    "source": {
        "type": "pdf | youtube_video | text | image | video_file",
        "_originalUrl": "https://youtube.com/...",
        "_originalFilename": "lecture_notes.pdf",
        "_gcsPath": "coll-id/originals/mat-id.pdf",
        "_rawText": "..."
    },
    "status": "uploaded | extracting | transcribing | classifying | chunking | enriching | ready | rejected | error",
    "errorDetail": null,
    "rejectReason": null,
    "classification": { "type": "lecture", "subjects": ["mechanics"], "difficulty": "intermediate", ... },
    "title": "Newton's Laws — Lecture 3",
    "chunkCount": 6,
    "duration": 1200,
    "addedAt": "datetime",
    "readyAt": "datetime"
}
```

#### `chunks`
```json
{
    "chunkId": "uuid",
    "materialId": "uuid",
    "collectionId": "uuid",
    "index": 0,
    "title": "Deriving the Kinematic Equations",
    "anchor": { "start": 120.0, "end": 330.0, "displayStart": "2:00", "displayEnd": "5:30" },
    "content": {
        "transcript": "So now let's derive...",
        "summary": "This section derives the four kinematic equations...",
        "keyPoints": ["v = v₀ + at applies when acceleration is constant"],
        "formulas": ["v = v_0 + at"],
        "concepts": ["kinematic_equations", "constant_acceleration"],
        "difficulty": "intermediate",
        "confidence": "high"
    },
    "linkedFrameIds": ["frame-uuid-1"],
    "media": { "hasVideo": true },
    "segments": [{ "text": "...", "start": 120.0, "end": 125.0 }],
    "embedding": null
}
```

### Layer 1 Collections (+2)

#### `topic_index`
```json
{
    "topicId": "uuid",
    "collectionId": "uuid",
    "name": "Kinematic Equations",
    "displayName": "Deriving and Applying the Kinematic Equations",
    "subject": "mechanics",
    "description": "The four kinematic equations for constant acceleration...",
    "difficulty": "intermediate",
    "order": 2,
    "chunkIds": ["chunk-uuid-1", "chunk-uuid-2"],
    "conceptNames": ["kinematic_equations", "constant_acceleration"],
    "prerequisites": ["vectors", "velocity"],
    "exerciseCount": 4
}
```

#### `flow_map`
```json
{
    "collectionId": "uuid",
    "version": 3,
    "generatedAt": "datetime",
    "chapters": [
        {
            "title": "Foundations of Motion",
            "subject": "mechanics",
            "topics": [
                { "topicId": "...", "order": 0, "estimatedMinutes": 15, "rationale": "No prerequisites" }
            ]
        }
    ],
    "topicPositions": { "topic-uuid": { "chapter": 0, "position": 0 } }
}
```

### Layer 2 Collections (+3)

#### `concept_graph`
```json
{
    "conceptId": "uuid",
    "collectionId": "uuid",
    "name": "Newton's Second Law",
    "normalizedName": "newtons_second_law",
    "aliases": ["F=ma", "Newton's 2nd Law"],
    "definition": "The net force on an object equals its mass times its acceleration",
    "formulas": ["F_net = ma"],
    "prerequisites": ["force", "mass", "acceleration"],
    "related": ["newtons_first_law", "newtons_third_law"],
    "locations": [{ "topicId": "...", "chunkId": "...", "role": "introduced" }]
}
```

#### `exercise_index`
```json
{
    "exerciseId": "uuid",
    "materialId": "uuid",
    "chunkId": "uuid",
    "collectionId": "uuid",
    "topicId": "topic-uuid",
    "statement": "A 5 kg block on a 30° incline... Find the acceleration.",
    "type": "numerical | conceptual | derivation | multiple_choice",
    "difficulty": "intermediate",
    "concepts": ["inclined_plane", "friction"],
    "hasDiagram": true,
    "diagramUrl": "gs://...",
    "solution": { "available": true, "steps": ["Draw FBD...", "Apply F=ma..."], "answer": "a = 3.27 m/s²" }
}
```

#### `student_progress`
```json
{
    "collectionId": "uuid",
    "userEmail": "student@example.com",
    "completedTopics": ["topic-uuid-1"],
    "completedChunks": ["chunk-uuid-1"],
    "currentPosition": { "topicId": "topic-uuid-3", "chunkIndex": 2 },
    "conceptMastery": {
        "newtons_second_law": {
            "level": "proficient",
            "tested": true,
            "lastSeen": "datetime",
            "observations": [{ "text": "Correctly applied F=ma to two-body problem", "at": "datetime" }]
        }
    }
}
```

#### `difficulty_map`
```json
{
    "collectionId": "uuid",
    "levels": {
        "beginner": [{ "topicId": "...", "name": "...", "conceptCount": 3 }],
        "intermediate": [...],
        "advanced": [...]
    }
}
```

### Layer 3 Collections (+2)

#### `extracted_frames`
```json
{
    "frameId": "uuid",
    "materialId": "uuid",
    "collectionId": "uuid",
    "timestamp": 185.0,
    "displayTime": "3:05",
    "classification": "board | equation | diagram | slide | chart",
    "contentDescription": "Free body diagram of block on inclined plane",
    "ocr": { "fullText": "F_N  F_g = mg  θ = 30°", "elements": [...] },
    "gcsPath": "coll-id/frames/mat-id/frame_000185.jpg",
    "gcsUrl": "gs://..."
}
```

#### `asset_index`
```json
{
    "assetId": "uuid",
    "collectionId": "uuid",
    "topicId": "topic-uuid",
    "type": "board | equation | diagram | slide | chart",
    "description": "Free body diagram of block on inclined plane",
    "frameId": "frame-uuid",
    "gcsUrl": "gs://...",
    "ocrText": "F_N  F_g = mg"
}
```

### Operational Collections (always present)

#### `transcripts`
```json
{
    "materialId": "uuid",
    "collectionId": "uuid",
    "source": "youtube_captions | elevenlabs_stt",
    "language": "en",
    "duration": 1200.0,
    "segments": [{ "text": "...", "start": 0.0, "end": 3.5, "speaker": 0, "confidence": 0.95 }],
    "fullText": "complete transcript...",
    "gcsPath": "coll-id/transcripts/mat-id.json"
}
```

#### `index_locks` / `merge_queue` (Layer 1+ operational)
```json
// index_locks
{ "collectionId": "uuid", "acquiredAt": "datetime", "expiresAt": "datetime" }
// merge_queue
{ "collectionId": "uuid", "materialId": "uuid", "queuedAt": "datetime" }
```

---

## 11. GCS Storage Layout

```
gs://capacity-materials/
  └── {collectionId}/
      ├── originals/
      │   ├── {materialId}.pdf
      │   ├── {materialId}.mp4          # (proposed — video files)
      │   └── {materialId}.jpg          # (proposed — images)
      ├── frames/
      │   └── {materialId}/
      │       ├── frame_000120.jpg      # video keyframe at t=120s
      │       └── page_001_img_0.jpg    # PDF embedded image
      └── transcripts/
          └── {materialId}.json
```

---

## 12. REST API Surface

### Core Endpoints (Implemented)

| Method | Path | Purpose | Layer |
|--------|------|---------|-------|
| `POST` | `/api/v1/collections` | Create collection | L0 |
| `GET` | `/api/v1/collections?userId=...` | List user's collections | L0 |
| `GET` | `/api/v1/collections/{id}` | Collection + materials | L0 |
| `GET` | `/api/v1/collections/{id}/status` | Processing progress | L0 |
| `POST` | `/api/v1/collections/{id}/materials` | Add YouTube/text/batch | L0 |
| `POST` | `/api/v1/collections/{id}/upload` | Upload PDF/txt file (50MB) | L0 |
| `POST` | `/api/v1/collections/{id}/reindex` | Full rebuild | L1 |

### Proposed Endpoints

| Method | Path | Purpose | Layer |
|--------|------|---------|-------|
| `DELETE` | `/api/v1/collections/{id}` | Delete collection (cascading) | L0 |
| `DELETE` | `/api/v1/collections/{cid}/materials/{mid}` | Delete material (cascading) | L0 |
| `GET` | `/api/v1/collections/{cid}/materials/{mid}/url` | Signed URL (60 min) | L1 |
| `POST` | `/api/v1/collections/{id}/upload` | Extend: images, video files | L3 |
| `GET` | `/api/v1/collections/{id}/search?q=...` | Vector search | L3 |

---

## 13. Material Query Layer (MQL)

The tutor's interface to content. Organized by layer:

### Layer 0 Tools (minimum)

| Tool | Purpose | Returns |
|------|---------|---------|
| `list_chunks(collectionId)` | Table of contents | Chunk titles + summaries |
| `read_chunk(chunkId)` | Read a section | Full transcript, key points, formulas |
| `search_content(collectionId, query)` | Keyword search | Matching chunks |

### Layer 1 Tools (+3)

| Tool | Purpose | Returns |
|------|---------|---------|
| `browse_topics(collectionId)` | All topics with progress | Topic list with difficulty, counts |
| `browse_topic(topicId)` | One topic in detail | Chunks, concepts, exercises for topic |
| `get_flow(collectionId)` | Teaching sequence | Chapters with ordered topics |

### Layer 2 Tools (+5)

| Tool | Purpose | Returns |
|------|---------|---------|
| `find_concept(name)` | Concept by name/alias | Definition, prerequisites, locations |
| `search_concepts(query)` | Fuzzy concept search | Matching concepts |
| `get_exercises(topicId?, difficulty?)` | Practice problems | Exercises with metadata |
| `get_mastery(collectionId)` | Student progress | Completed topics, mastery levels |
| `log_observation(conceptId, note)` | Record learning event | Confirmation |

### Layer 3 Tools (+2)

| Tool | Purpose | Returns |
|------|---------|---------|
| `semantic_search(collectionId, query)` | Vector similarity search | Top-K chunks by meaning |
| `get_assets(topicId?, type?)` | Visual assets | Diagrams, frames with URLs |

---

## 14. Vector Search & Embeddings

### Current State (Layer 0-2)
`search_content` uses MongoDB `$regex` — pure keyword matching.

### Proposed (Layer 3)

**Embedding model**: OpenAI `text-embedding-3-small` (1536 dim, ~$0.02/1M tokens)

**What gets embedded** (during enrichment):
- Chunk: `"{title}. {summary}. Concepts: {concepts joined}"`

**Storage**: `chunks.embedding` field (1536-dim float array)

**Index**: MongoDB Atlas Vector Search:
```json
{
    "type": "vectorSearch",
    "definition": {
        "fields": [{
            "type": "vector",
            "path": "embedding",
            "numDimensions": 1536,
            "similarity": "cosine"
        }]
    }
}
```

**Query**:
```python
async def semantic_search(collection_id: str, query: str, limit: int = 5):
    embedding = await embed_text(query)
    return await db.chunks.aggregate([
        {
            "$vectorSearch": {
                "index": "chunk_embedding_index",
                "path": "embedding",
                "queryVector": embedding,
                "numCandidates": 50,
                "limit": limit,
                "filter": { "collectionId": collection_id }
            }
        },
        { "$project": { "chunkId": 1, "title": 1, "content.summary": 1, "score": { "$meta": "vectorSearchScore" } } }
    ]).to_list(None)
```

**Fallback** (non-Atlas): Qdrant or Chroma sidecar with the same tool interface.

---

## 15. Incremental Update & Merge Strategy

Students add materials over time. Each addition:
1. Processes independently (stages 0-6)
2. Merges into existing topic/concept structure (stage 8)
3. Re-sequences the flow map (stage 9)

### Merge Flow
```
New PDF uploaded
  → process_material() runs stages 0-6 independently
  → Stage 8: acquire lock on collectionId
      → If locked: queue in merge_queue, return
      → LLM merges chunks into existing or new topics
      → LLM deduplicates concepts
      → Link exercises, catalog assets
      → Rebuild difficulty map, re-generate flow map
      → Release lock → drain queue
```

### Concurrent Safety
- MongoDB lock per collection in `index_locks` (5-min timeout, stale locks stolen)
- Queue in `merge_queue` — drained FIFO after lock release

---

## 16. Deletion Pipeline (Cascading)

### DELETE Material
```
DELETE /api/v1/collections/{cid}/materials/{mid}
  ├─ MongoDB cascading delete:
  │   ├─ chunks (materialId = mid)
  │   ├─ transcripts (materialId = mid)
  │   ├─ extracted_frames (materialId = mid)
  │   ├─ exercise_index (materialId = mid)
  │   └─ asset_index (materialId = mid)
  ├─ Topic cleanup: $pull chunkIds, delete empty topics
  ├─ Concept cleanup: $pull locations, delete orphaned concepts
  ├─ Re-sequence: rebuild difficulty_map + flow_map
  ├─ GCS cleanup: originals + frames for this material
  ├─ Delete material document
  └─ Update collection stats
```

### DELETE Collection
```
DELETE /api/v1/collections/{cid}
  ├─ Bulk delete: chunks, transcripts, frames, exercises,
  │   topics, concepts, assets, flow_map, difficulty_map, locks, queue
  ├─ Delete all materials
  ├─ Delete student_progress
  ├─ Delete GCS folder (recursive)
  └─ Delete collection document
```

---

## 17. Teaching Context — How the Tutor Sees BYO Content

### Activation
Frontend sends `collectionId` in student profile. Chat route detects it and switches to BYO mode.

### Lean Context (~600-800 tokens)
Injected into system prompt. NOT the full content — just a snapshot:

```
[Collection: Physics 101 — My Notes]
Subjects: classical mechanics, thermodynamics | 8 topics, 47 chunks, 15 exercises

Sequence: Foundations (3 topics) → Dynamics (2 topics) → Energy (3 topics)

[Student Progress]
Completed: 2 topics | Current: Newton's Second Law
Weak concepts: friction, circular_motion

[Tools Available]
  browse_topics() — list topics
  read_chunk(id) — read a section
  search(query) — find content
  ...
```

The tutor navigates content on-demand using MQL tools — never receives raw material dumps.

### Prompt Structure
```
TUTOR_SYSTEM_PROMPT (personality, pedagogy)
  + MQL_TOOLKIT_PROMPT (tool instructions)
  + lean context snapshot
  + student profile + student model
```

---

## 18. Frontend Integration Points

### What Needs to Be Built

| Component | What It Does | Layer |
|-----------|-------------|-------|
| Enable BYO card | Remove `if (cid === 'byo') return` guard | L0 |
| Collection creation | Name → create via POST | L0 |
| Upload UI | Drag-drop zone: PDF, text paste, YouTube URL | L0 |
| Processing status | Poll `GET /status`, per-material progress | L0 |
| Wire `collectionId` | `buildContext()` sends collectionId in profile | L0 |
| Material list + delete | Browse uploads, remove materials | L0 |
| Raw material viewer | Signed URL access to original files | L1 |

### Context Wiring (Critical)

`buildContext()` currently sends `{ courseId, studentName, ... }`.
For BYO: must also send `{ collectionId: "uuid" }`.
Chat route's `_extract_collection_id()` reads this and activates BYO mode.

---

## 19. External Dependencies & Cost Model

| Service | Used For | Layer | Cost |
|---------|----------|-------|------|
| **Claude Sonnet** | Topic detection, concept merge, flow map, chunking | L1+ | ~$0.05-0.15/material |
| **Claude Haiku** | Classification, enrichment, exercises | L1+ | ~$0.01-0.03/material |
| **Claude Vision** | Frame classification, OCR | L3 | ~$0.01-0.05/video |
| **YouTube Captions** | Free transcription | L0 | Free |
| **ElevenLabs STT** | Transcription fallback, non-YouTube | L0 | ~$0.01/min |
| **OpenAI Embeddings** | Vector embeddings | L3 | ~$0.001/material |
| **GCS** | File storage | L0 | ~$0.02/GB/month |
| **MongoDB Atlas** | All data + vector search | L0 | Existing |

**Per-material cost**:
- Layer 0: ~$0.005 (nearly free — no LLM in pipeline)
- Layer 0+1: ~$0.05-0.15 (LLM for chunking + topic detection)
- Full stack: ~$0.10-0.25

---

## 20. Production Concerns

### Rate Limits
- Uploads: 10/min, 100/day per user
- Max concurrent pipeline tasks per collection: 5

### File Size Limits
- PDF: 50MB | Video: 500MB | Image: 10MB | Text: 1MB | Collection total: 2GB

### Error Recovery
- Each material processes independently — one failure doesn't block others
- Failed materials can be retried
- Per-stage status tracking visible via API

### Security
- GCS: signed URLs only (60-min expiry)
- User-scoped collection access (userId check on all endpoints)
- File upload validation (magic bytes, no executables)

---

## 21. Implementation Status & Gaps

### What's Built

| Component | Layer | Files |
|-----------|-------|-------|
| Collection CRUD | L0 | `ingestion.py` |
| Material upload (PDF, YouTube, text) | L0 | `ingestion.py`, `orchestrator.py` |
| Full 10-stage pipeline | L0-L2 | `orchestrator.py`, `extractors/*`, `processors/*` |
| Incremental merge with locking | L1 | `index_builder.py` |
| Flow map generation | L1 | `sequencer.py` |
| 12 MQL tools | L0-L2 | `mql.py`, `tools/__init__.py` |
| Lean context builder | L0 | `lean_context.py` |
| Chat route BYO branch | L0 | `chat.py` |
| GCS storage | L0 | `gcs.py` |
| MongoDB indexes | L0-L2 | `byo_indexes.py` |

### What's Missing

| Gap | Layer | Effort |
|-----|-------|--------|
| Material deletion + cascading cleanup | L0 | 1-2 days |
| Collection deletion | L0 | 0.5 day |
| Frontend: upload UI + collection management | L0 | 3-4 days |
| Frontend: wire `collectionId` into context | L0 | 0.5 day |
| Image source type | L3 | 1-2 days |
| Vector embeddings + semantic search | L3 | 2-3 days |
| Signed URL endpoint | L1 | 0.5 day |
| ElevenLabs STT adapter | L0 | 1 day |
| Video file upload (MP4/MOV) | L3 | 2-3 days |
| PPTX / DOCX support | L3 | 1-2 days |

### Recommended Rollout

| Week | What Ships | What Works |
|------|-----------|-----------|
| **Week 1** | Layer 0: Extract + chunk + store + search + read + frontend upload + deletion | Students upload PDFs/YouTube/text, tutor teaches from content, ad-hoc questions work |
| **Week 2** | Layer 1: Smart chunking + topics + flow map + classification | Structured courses, "teach me from topic X", crash courses |
| **Week 3** | Layer 2: Concepts + exercises + progress tracking | Assessment from real exam papers, mastery tracking, spaced repetition |
| **When needed** | Layer 3: Vector search + frames + images + video files | Fuzzy queries, visual assets, all file types |
