# BYO Material Ingestion Pipeline — Architecture Specification

> **Status**: Backend pipeline 70% complete, Frontend 0%, Vector search 0%, Deletion 0%
> **Last updated**: March 2026
> **Audience**: Engineering team — covers schema, APIs, pipeline, retrieval, and production concerns

---

## Table of Contents

1. [Overview](#1-overview)
2. [System Architecture](#2-system-architecture)
3. [Source Types & Ingestion Matrix](#3-source-types--ingestion-matrix)
4. [Pipeline Stages (Detailed)](#4-pipeline-stages-detailed)
5. [MongoDB Schema (All Collections)](#5-mongodb-schema-all-collections)
6. [GCS Storage Layout](#6-gcs-storage-layout)
7. [REST API Surface](#7-rest-api-surface)
8. [Material Query Layer (MQL) — 12 Tools](#8-material-query-layer-mql--12-tools)
9. [Vector Search & Embeddings](#9-vector-search--embeddings)
10. [Incremental Update & Merge Strategy](#10-incremental-update--merge-strategy)
11. [Deletion Pipeline (Cascading)](#11-deletion-pipeline-cascading)
12. [Teaching Context — How the Tutor Sees BYO Content](#12-teaching-context--how-the-tutor-sees-byo-content)
13. [Student Use Cases & Retrieval Paths](#13-student-use-cases--retrieval-paths)
14. [Frontend Integration Points](#14-frontend-integration-points)
15. [External Dependencies & Cost Model](#15-external-dependencies--cost-model)
16. [Production Concerns](#16-production-concerns)
17. [Implementation Status & Gaps](#17-implementation-status--gaps)

---

## 1. Overview

The BYO (Bring Your Own) system lets students upload their own course materials — PDFs, YouTube videos, playlists, images, text notes — and have them processed into a structured, queryable library that the AI tutor can teach from.

**Core principle**: The tutor never receives raw material dumps. Instead, it gets a lean context snapshot (~600 tokens) and uses 12 MQL (Material Query Layer) tools to discover and read content on-demand — identical UX to how a teacher with a textbook works: browse the table of contents, flip to a page, read it, teach from it.

**Pipeline in one sentence**: Upload → Extract → Transcribe → Classify → Chunk → Enrich → Index → Sequence → Teach.

---

## 2. System Architecture

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
│  ┌──────▼──────────────────────────────────────┐                     │
│  │            Processing Pipeline               │                     │
│  │  Extract → Transcribe → Frames → Classify   │                     │
│  │  → Chunk → Enrich → Exercises → Merge Index  │                     │
│  │  → Sequence                                   │                     │
│  └──────┬──────────────────────────────────────┘                     │
└─────────┼─────────────────────────────────────────────────────────────┘
          │
    ┌─────▼─────┐  ┌──────────┐  ┌──────────────────┐  ┌────────────┐
    │  MongoDB   │  │   GCS    │  │ ElevenLabs /     │  │ Anthropic  │
    │ (11 colls) │  │ (blobs)  │  │ YouTube Captions │  │ Claude     │
    └───────────┘  └──────────┘  └──────────────────┘  └────────────┘
```

---

## 3. Source Types & Ingestion Matrix

| Source Type | Upload Method | Extraction | Transcription | Frame Extraction | Status |
|-------------|--------------|------------|---------------|------------------|--------|
| **PDF** | Multipart file upload (50MB max) | PyMuPDF (text + embedded images) | N/A | Embedded images extracted, uploaded to GCS | **Implemented** |
| **YouTube Video** | URL (single) | yt-dlp metadata | YouTube captions → ElevenLabs fallback | ffmpeg keyframes → Claude Vision classify + OCR | **Implemented** |
| **YouTube Playlist** | URL (playlist) | yt-dlp playlist expansion → individual videos | Per-video (see above) | Per-video (see above) | **Implemented** |
| **Text Paste** | JSON body (`{type: "text", content: "..."}`) | Normalization + structure detection | N/A | N/A | **Implemented** |
| **Text File** (txt, md) | Multipart file upload | UTF-8 decode → text pipeline | N/A | N/A | **Implemented** |
| **Image** (JPG, PNG) | Multipart file upload | Claude Vision OCR + classification | N/A | The image itself is the "frame" | **Not implemented** |
| **Video File** (MP4, MOV) | Multipart file upload → GCS | N/A (no yt-dlp needed) | ElevenLabs Speech-to-Text | ffmpeg keyframes → Claude Vision | **Not implemented** |
| **PPTX** | Multipart file upload | python-pptx slide extraction | N/A | Slide renders as images | **Not implemented** |
| **DOCX** | Multipart file upload | python-docx text extraction | N/A | Embedded images | **Not implemented** |
| **Batch URLs** | JSON body (`{type: "batch", items: [...]}`) | Per-item dispatch | Per-item | Per-item | **Implemented** |

### Transcription Strategy (Updated)

Current cascade for YouTube:
1. **YouTube Captions** (free, fast) — `youtube-transcript-api`
2. **Deepgram Nova-2** (paid fallback) — when captions unavailable

**Proposed change**: Replace Deepgram with **ElevenLabs Speech-to-Text** for non-YouTube videos and as YouTube fallback:
- ElevenLabs provides both TTS and STT — consolidates vendor
- Cost-effective for our volume (we already pay for TTS)
- Supports direct audio URL or file upload
- Provides word-level timestamps suitable for segment generation

Cascade becomes:
1. YouTube Captions (free, YouTube only)
2. ElevenLabs STT (paid, universal fallback — works for MP4/MOV/YouTube)

---

## 4. Pipeline Stages (Detailed)

Each material runs through a 10-step pipeline as a background `asyncio.create_task()`. Material becomes "ready" (teachable) after step 6. Steps 7-9 run asynchronously afterward.

### Stage 0: VALIDATE
**Purpose**: Pre-flight checks before any processing.
**Checks**:
- YouTube URL format validation
- PDF: not encrypted, >0 pages, extractable text in first 3 pages (>100 chars)
- Text: minimum 50 chars, >50% alphanumeric ratio (catches binary/gibberish)
- Image (proposed): valid image format, minimum dimensions (100x100)
- Video file (proposed): valid container, duration check (<4 hours)

**Failure mode**: Material status → `rejected` with reason. Collection progress updated.

### Stage 1: EXTRACT
**Purpose**: Get raw content from the source.

| Source | Extractor | Output |
|--------|-----------|--------|
| YouTube | `yt-dlp` metadata fetch | Title, duration, thumbnail, description |
| YouTube Playlist | `yt-dlp` flat extraction | List of video URLs → creates child materials |
| PDF | `PyMuPDF` | Per-page text + embedded images (uploaded to GCS) |
| Text | `normalize_text()` | Cleaned text with structure hints |
| Image (proposed) | Claude Vision | OCR text + content classification + description |
| Video file (proposed) | ffprobe metadata | Duration, resolution, codec info |

### Stage 2: TRANSCRIBE (audio/video only)
**Purpose**: Speech → timestamped text segments.

```python
@dataclass
class Segment:
    text: str        # utterance text
    start: float     # seconds
    end: float       # seconds
    speaker: int     # speaker ID (diarization)
    confidence: float
```

**YouTube**: Captions API → ElevenLabs STT fallback
**Video file** (proposed): ElevenLabs STT (direct audio upload)

Transcripts stored in MongoDB `transcripts` collection with GCS backup path.

### Stage 3: FRAME EXTRACT (video only)
**Purpose**: Extract and classify visual content (board work, equations, diagrams).

1. **ffmpeg** extracts keyframes at scene changes (~1 frame per 5-10 seconds)
2. **Claude Vision** classifies each frame:
   - `board` — handwritten content on whiteboard/chalkboard
   - `equation` — mathematical formula prominently displayed
   - `diagram` — figure, graph, chart, circuit, etc.
   - `slide` — presentation slide with text
   - `chart` — data visualization
   - `talking_head` — instructor only (discarded)
   - `transition` — blank/title card (discarded)
3. **Claude Vision OCR** extracts text from educational frames
4. Frames uploaded to GCS, metadata stored in `extracted_frames`

### Stage 4: CLASSIFY
**Purpose**: Material type and subject detection using LLM (Haiku — cheap, fast).

```python
@dataclass
class Classification:
    type: str           # lecture | assignment | exercise_set | reference | notes | mixed
    subjects: list[str] # ["classical mechanics", "kinematics"]
    difficulty: str     # beginner | intermediate | advanced
    is_structured: bool # has headings / numbered sections
    has_exercises: bool # contains practice problems
    language: str       # "en"
    confidence: float   # 0.0 - 1.0
    educational_quality: str  # high | medium | low | non_educational
    title_suggestion: str
```

### Stage 4b: QUALITY GATE
**Purpose**: Reject low-quality or non-educational material.
**Rejection criteria**:
- Classification confidence < 0.4
- Extracted text < 200 chars
- `educational_quality == "non_educational"`
- Video > 4 hours

### Stage 5: CHUNK
**Purpose**: Semantic section splitting. Strategy depends on material type.

| Material Type | Strategy | Target Size |
|--------------|----------|-------------|
| Video transcript | LLM detects topic boundaries using timestamps | 3-7 min per chunk |
| Assignment / exercise set | LLM splits into individual problems | 1 problem per chunk |
| Structured text (has headings) | LLM follows heading hierarchy (H1 = boundary, H2 = usually boundary, H3 = merge into parent) | 300-3000 chars |
| Unstructured text | Paragraph-boundary splitting | ~1500 chars |

**Fallbacks**: Fixed-time chunks (3 min) for video, fixed-char chunks (1500) for text.

```python
@dataclass
class RawChunk:
    index: int
    title: str          # descriptive, not "Section 3"
    anchor: Anchor      # start/end in seconds (video) or char offset (text)
    text: str           # raw content
    topic_summary: str  # one-line summary
    segments: list      # original transcript segments (video)
    is_exercise: bool
```

### Stage 6: ENRICH (per-chunk, parallelized)
**Purpose**: Extract structured knowledge from each chunk.

LLM (Haiku) extracts per-chunk:
- **Summary** (2-3 sentences, student-facing)
- **Key Points** (3-6 actionable takeaways)
- **Concepts** with definitions and roles (introduced / prerequisite / applied)
- **Formulas** (standard notation, not LaTeX)
- **Difficulty** rating
- **Linked frame IDs** (video frames within chunk's time range)

```python
# Stored in MongoDB chunks collection:
{
    "chunkId": "uuid",
    "materialId": "uuid",
    "collectionId": "uuid",
    "index": 0,
    "title": "Deriving the Kinematic Equations",
    "anchor": { "start": 120.0, "end": 330.0, "displayStart": "2:00", "displayEnd": "5:30" },
    "content": {
        "transcript": "full text...",
        "summary": "This section derives...",
        "keyPoints": ["v = v₀ + at applies when...", ...],
        "formulas": ["v = v_0 + at", "x = x_0 + v_0*t + (1/2)*a*t^2"],
        "concepts": ["kinematic_equations", "constant_acceleration"],
        "difficulty": "intermediate",
        "confidence": "high"
    },
    "linkedFrameIds": ["frame-uuid-1", "frame-uuid-2"],
    "media": { "hasVideo": true },
    "segments": [{ "text": "...", "start": 120.0, "end": 125.0 }, ...]
}
```

**Material status → `ready` here.** Collection progress updated. Teaching can begin.

### Stage 7: EXERCISES (background)
**Purpose**: Extract practice problems from exercise-flagged chunks.

LLM distinguishes:
- **Exercises** (student solves) → extracted
- **Worked examples** (instructor solves, shown step-by-step) → skipped

```python
@dataclass
class Exercise:
    exercise_id: str
    material_id: str
    chunk_id: str
    collection_id: str
    statement: str           # full problem text
    type: str                # numerical | conceptual | derivation | multiple_choice
    difficulty: str
    concepts: list[str]
    has_diagram: bool
    diagram_frame_id: str    # linked video frame with diagram
    diagram_url: str
    solution: {
        "available": bool,
        "steps": list[str],
        "answer": str
    }
    topic_id: str            # linked during index merge
```

### Stage 8: MERGE INDEXES (incremental, locked)
**Purpose**: Organize chunks across materials into a coherent topic + concept structure.

This is the most complex stage. Runs after EACH material (not batched). Uses MongoDB-based locking with a queue for concurrent merges.

**Sub-steps**:

1. **Topic detection / merge**: LLM assigns new chunks to existing topics or creates new ones
   - `add_to_existing`: chunk covers same topic → `$addToSet chunkIds`
   - `create_new`: genuinely new topic → new `topic_index` document
   - Overlap scoring (0.0 = new, 1.0 = duplicate)

2. **Concept graph merge**: LLM deduplicates new concept mentions against existing graph
   - `map_to_existing`: "F=ma" maps to existing "Newton's Second Law" concept
   - `create_new`: genuinely new concept → new `concept_graph` document with definition, prerequisites, formulas, aliases

3. **Exercise linking**: Exercises linked to topics via concept overlap (set intersection)

4. **Asset cataloging**: Video frames classified as `board/equation/diagram/slide/chart` → `asset_index`

5. **Difficulty map rebuild**: Topics bucketed into beginner/intermediate/advanced

### Stage 9: SEQUENCE (flow map generation)
**Purpose**: Generate the recommended teaching order.

LLM produces a chapter → topic sequence:
```json
{
    "chapters": [
        {
            "title": "Foundations of Motion",
            "subject": "mechanics",
            "topics": [
                { "topicId": "...", "order": 0, "estimatedMinutes": 15, "rationale": "No prerequisites" },
                { "topicId": "...", "order": 1, "estimatedMinutes": 25, "rationale": "Builds on vectors" }
            ]
        }
    ]
}
```

Ordering rules enforced by prompt:
- Prerequisites before dependents
- Definitions → laws → problem-solving → exercises
- Easier before harder (when no dependency)

Flow map versioned — re-generated after each incremental merge.

---

## 5. MongoDB Schema (All Collections)

### Database: `capacity` (content database)

#### `content_collections`
```json
{
    "collectionId": "uuid",
    "userId": "user-id",
    "type": "byo",
    "title": "Physics 101 — My Notes",
    "status": "processing | partial | ready | error",
    "processingProgress": {
        "totalMaterials": 5,
        "processedMaterials": 3,
        "rejectedMaterials": 1,
        "currentStep": "enriching",
        "errors": []
    },
    "subjects": ["classical mechanics", "thermodynamics"],
    "stats": {
        "totalMaterials": 4,
        "totalChunks": 47,
        "totalConcepts": 32,
        "totalExercises": 15,
        "totalTopics": 8
    },
    "createdAt": "datetime",
    "updatedAt": "datetime"
}
```
**Indexes**: `userId`, `status`

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
        "_rawText": "...",
        "_fileBytes": null
    },
    "status": "uploaded | extracting | transcribing | framing | classifying | chunking | enriching | ready | rejected | error",
    "errorDetail": null,
    "rejectReason": null,
    "classification": {
        "type": "lecture",
        "subjects": ["mechanics"],
        "difficulty": "intermediate",
        "hasExercises": false,
        "isStructured": true,
        "language": "en",
        "confidence": 0.92,
        "educationalQuality": "high"
    },
    "title": "Newton's Laws — Lecture 3",
    "chunkCount": 6,
    "duration": 1200,
    "pageCount": null,
    "thumbnailUrl": "https://img.youtube.com/...",
    "addedAt": "datetime",
    "readyAt": "datetime"
}
```
**Indexes**: `collectionId`, `(collectionId, status)`, `source._originalUrl` (sparse)

#### `chunks`
```json
{
    "chunkId": "uuid",
    "materialId": "uuid",
    "collectionId": "uuid",
    "index": 0,
    "title": "Deriving the Kinematic Equations",
    "anchor": {
        "start": 120.0,
        "end": 330.0,
        "displayStart": "2:00",
        "displayEnd": "5:30"
    },
    "content": {
        "transcript": "So now let's derive...",
        "summary": "This section derives the four kinematic equations...",
        "keyPoints": ["v = v₀ + at applies when acceleration is constant", "..."],
        "formulas": ["v = v_0 + at", "x = x_0 + v_0*t + (1/2)*a*t^2"],
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
**Indexes**: `collectionId`, `materialId`, `(collectionId, materialId, index)`
**Proposed**: `embedding` field (1536-dim float array) + Atlas Vector Search index

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
    "gcsPath": "coll-id/transcripts/mat-id.json",
    "createdAt": "datetime"
}
```
**Indexes**: `materialId` (unique), `collectionId`

#### `extracted_frames`
```json
{
    "frameId": "uuid",
    "materialId": "uuid",
    "collectionId": "uuid",
    "timestamp": 185.0,
    "displayTime": "3:05",
    "classification": "board | equation | diagram | slide | chart",
    "contentDescription": "Whiteboard showing free body diagram of block on inclined plane",
    "ocr": {
        "fullText": "F_N  F_g = mg  θ = 30°",
        "elements": [
            { "type": "equation", "text": "F_g = mg", "confidence": 0.9 },
            { "type": "label", "text": "θ = 30°", "confidence": 0.85 }
        ]
    },
    "gcsPath": "coll-id/frames/mat-id/frame_000185.jpg",
    "gcsUrl": "gs://capacity-materials/...",
    "quality": "high",
    "isKeyFrame": true
}
```
**Indexes**: `materialId`, `collectionId`, `(materialId, timestamp)`, `classification`

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
    "chunkIds": ["chunk-uuid-1", "chunk-uuid-2", "chunk-uuid-3"],
    "conceptNames": ["kinematic_equations", "constant_acceleration", "displacement"],
    "prerequisites": ["vectors", "velocity", "acceleration"],
    "successors": ["projectile_motion"],
    "exerciseCount": 4,
    "createdAt": "datetime"
}
```
**Indexes**: `collectionId`, `(collectionId, order)`

#### `concept_graph`
```json
{
    "conceptId": "uuid",
    "collectionId": "uuid",
    "name": "Newton's Second Law",
    "normalizedName": "newtons_second_law",
    "aliases": ["F=ma", "Newton's 2nd Law", "second law of motion"],
    "definition": "The net force on an object equals its mass times its acceleration",
    "category": "dynamics",
    "subject": "mechanics",
    "difficulty": "intermediate",
    "formulas": ["F_net = ma"],
    "prerequisites": ["force", "mass", "acceleration"],
    "related": ["newtons_first_law", "newtons_third_law"],
    "locations": [
        { "topicId": "topic-uuid", "chunkId": "chunk-uuid", "role": "introduced" }
    ],
    "createdAt": "datetime"
}
```
**Indexes**: `collectionId`, `(normalizedName, collectionId)`, `aliases`

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
    "concepts": ["inclined_plane", "friction", "newtons_second_law"],
    "hasDiagram": true,
    "diagramDescription": "Block on inclined plane with force vectors",
    "diagramFrameId": "frame-uuid",
    "diagramUrl": "gs://...",
    "solution": { "available": true, "steps": ["Draw FBD...", "Apply F=ma..."], "answer": "a = 3.27 m/s²" },
    "createdAt": "datetime"
}
```
**Indexes**: `collectionId`, `(collectionId, difficulty)`, `topicId`, `concepts`

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
                { "topicId": "...", "order": 0, "estimatedMinutes": 15, "rationale": "Starting point" }
            ]
        }
    ],
    "topicPositions": { "topic-uuid": { "chapter": 0, "position": 0 } }
}
```
**Indexes**: `collectionId` (unique)

#### `difficulty_map`
```json
{
    "collectionId": "uuid",
    "levels": {
        "beginner": [{ "topicId": "...", "name": "...", "conceptCount": 3 }],
        "intermediate": [...],
        "advanced": [...]
    },
    "topicCount": 8,
    "conceptCount": 32,
    "updatedAt": "datetime"
}
```
**Indexes**: `collectionId` (unique)

#### `asset_index`
```json
{
    "assetId": "uuid",
    "collectionId": "uuid",
    "topicId": "topic-uuid",
    "type": "board | equation | diagram | slide | chart",
    "description": "Free body diagram of block on inclined plane",
    "materialId": "uuid",
    "frameId": "frame-uuid",
    "timestamp": 185.0,
    "gcsPath": "coll-id/frames/mat-id/frame_000185.jpg",
    "gcsUrl": "gs://...",
    "ocrText": "F_N  F_g = mg  θ = 30°",
    "createdAt": "datetime"
}
```
**Indexes**: `collectionId`, `topicId`, `type`

#### `index_locks` (operational)
```json
{
    "collectionId": "uuid",
    "acquiredAt": "datetime",
    "expiresAt": "datetime"
}
```

#### `merge_queue` (operational)
```json
{
    "collectionId": "uuid",
    "materialId": "uuid",
    "queuedAt": "datetime"
}
```

### Database: `tutor_v2` (student state)

#### `student_progress`
```json
{
    "collectionId": "uuid",
    "userEmail": "student@example.com",
    "completedTopics": ["topic-uuid-1", "topic-uuid-2"],
    "completedChunks": ["chunk-uuid-1", "chunk-uuid-2"],
    "currentPosition": { "topicId": "topic-uuid-3", "chunkIndex": 2 },
    "conceptMastery": {
        "newtons_second_law": {
            "level": "proficient",
            "tested": true,
            "lastSeen": "datetime",
            "observations": [
                { "text": "Correctly applied F=ma to two-body problem", "at": "datetime", "sessionId": "..." }
            ]
        }
    },
    "sessionCount": 5,
    "lastSessionAt": "datetime"
}
```
**Indexes**: `(collectionId, userEmail)` (unique), `userEmail`

---

## 6. GCS Storage Layout

```
gs://capacity-materials/
  └── {collectionId}/
      ├── originals/
      │   ├── {materialId}.pdf          # Original uploaded PDF
      │   ├── {materialId}.mp4          # Original uploaded video (proposed)
      │   └── {materialId}.jpg          # Original uploaded image (proposed)
      ├── frames/
      │   └── {materialId}/
      │       ├── frame_000120.jpg      # Video keyframe at t=120s
      │       ├── frame_000185.jpg
      │       ├── page_001_img_0.jpg    # PDF embedded image (page 1, image 0)
      │       └── page_003_img_1.jpg
      └── transcripts/
          └── {materialId}.json         # Full transcript backup
```

---

## 7. REST API Surface

### Existing Endpoints (Implemented)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/collections` | Create collection `{ title, userId }` |
| `GET` | `/api/v1/collections?userId=...` | List user's collections |
| `GET` | `/api/v1/collections/{id}` | Collection details + materials |
| `GET` | `/api/v1/collections/{id}/status` | Processing status (poll this) |
| `POST` | `/api/v1/collections/{id}/materials` | Add YouTube/text/batch materials |
| `POST` | `/api/v1/collections/{id}/upload` | Upload PDF/text file (multipart, 50MB) |
| `POST` | `/api/v1/collections/{id}/reindex` | Full rebuild of indexes |

### Proposed New Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `DELETE` | `/api/v1/collections/{id}` | Delete entire collection (cascading) |
| `DELETE` | `/api/v1/collections/{cid}/materials/{mid}` | Delete single material (cascading) |
| `GET` | `/api/v1/collections/{cid}/materials/{mid}/url` | Signed URL for original file (60 min expiry) |
| `POST` | `/api/v1/collections/{id}/upload` | **Extend** to accept images (JPG/PNG) and video files (MP4/MOV) |
| `GET` | `/api/v1/collections/{id}/search?q=...` | Vector similarity search across chunks (proposed) |

---

## 8. Material Query Layer (MQL) — 12 Tools

The tutor uses these tools to explore and read content on-demand. All tools are scoped to the active `collectionId`.

| # | Tool | Purpose | Returns |
|---|------|---------|---------|
| 1 | `browse_topics()` | List all topics with progress | Topic list with difficulty, exercise counts |
| 2 | `browse_topic(topicId)` | Open one topic | Chunks, concepts, exercises, assets for topic |
| 3 | `get_flow()` | Teaching sequence | Chapters with ordered topics |
| 4 | `read_chunk(chunkId)` | Read full content | Transcript, key points, formulas, linked visuals |
| 5 | `search_content(query)` | Text search across chunks | Matching chunks with summaries |
| 6 | `grep_material(materialId, query)` | Search within one material | Matching chunks |
| 7 | `find_concept(name)` | Concept by name/alias | Definition, prerequisites, formulas, locations |
| 8 | `search_concepts(query)` | Fuzzy concept search | Matching concepts with definitions |
| 9 | `get_exercises(topicId?, difficulty?)` | Get practice problems | Exercise statements with metadata |
| 10 | `get_mastery()` | Student progress | Completed topics, concept mastery levels |
| 11 | `log_observation(conceptId, observation)` | Record mastery observation | Confirmation |
| 12 | `get_assets(topicId?, type?)` | Teaching assets | Diagrams, frames with descriptions and URLs |

### Proposed: Tool #13 — `semantic_search(query, limit?)`
Vector similarity search across chunk embeddings. Returns top-K semantically similar chunks regardless of exact keyword match. Essential for handling student queries like "explain that derivation" or "the energy conservation thing".

---

## 9. Vector Search & Embeddings

### Current State
`search_content` and `search_concepts` use MongoDB `$regex` — pure keyword matching. This fails for:
- Synonyms: "velocity" vs "speed of the object"
- Paraphrasing: "how energy is conserved" vs "law of conservation of energy"
- Conceptual queries: "the equation we derived in lecture 3" has no keyword overlap with the actual chunk

### Proposed Implementation

**Embedding model**: OpenAI `text-embedding-3-small` (1536 dim, $0.02/1M tokens — negligible cost)

**What gets embedded** (during enrichment, stage 6):
- Chunk: `f"{title}. {summary}. Concepts: {', '.join(concepts)}"`
- Concept: `f"{name}: {definition}"`

**Storage**: `chunks.embedding` field (1536-dim float array)

**Index**: MongoDB Atlas Vector Search index on `chunks.embedding`:
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

**Query** (new MQL tool `semantic_search`):
```python
async def semantic_search(collection_id: str, query: str, limit: int = 5) -> str:
    embedding = await embed_text(query)  # OpenAI embedding
    results = await db.chunks.aggregate([
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
    # Format results for tutor
```

**Fallback** (if not on Atlas): Use a sidecar vector store (Qdrant, Chroma) with the same interface.

---

## 10. Incremental Update & Merge Strategy

### Why Incremental?
Students add materials over time — not a one-shot bulk upload. After uploading a PDF, they might add YouTube videos a day later, then paste their notes. Each addition should:
1. Process independently (no re-processing existing materials)
2. Merge into the existing topic/concept structure
3. Re-sequence the flow map

### How It Works

```
Student uploads new PDF
  → create_material() inserts material doc
  → asyncio.create_task(process_material(material_id, collection_id))
  → Pipeline runs stages 0-6 independently
  → Stage 8: merge_into_indexes()
      → Acquire MongoDB lock (prevents concurrent merges)
      → If lock held: queue merge, return (processed when lock releases)
      → LLM decides: add chunks to existing topics or create new ones
      → LLM merges concepts: deduplicates against existing graph
      → Link exercises, catalog assets
      → Rebuild difficulty map
      → Re-generate flow map (version incremented)
      → Release lock → process queued merges
```

### Concurrent Safety
- MongoDB-based lock per collection: `index_locks` collection
- Lock timeout: 5 minutes (stale locks are stolen)
- Queue: `merge_queue` collection — stores pending merges when lock is held
- After releasing lock: all queued merges processed sequentially

---

## 11. Deletion Pipeline (Cascading)

### DELETE Material

```
DELETE /api/v1/collections/{cid}/materials/{mid}
  │
  ├─ 1. Load material document (get source info for GCS cleanup)
  ├─ 2. Delete from MongoDB:
  │    ├─ chunks where materialId = mid
  │    ├─ transcripts where materialId = mid
  │    ├─ extracted_frames where materialId = mid
  │    ├─ exercise_index where materialId = mid
  │    └─ asset_index where materialId = mid
  │
  ├─ 3. Topic cleanup:
  │    ├─ For each topic: $pull chunkIds belonging to this material
  │    ├─ Delete topics with 0 remaining chunkIds (empty topics)
  │    └─ Recalculate exerciseCount for affected topics
  │
  ├─ 4. Concept cleanup:
  │    ├─ For each concept: $pull locations referencing deleted chunks
  │    └─ Delete concepts with 0 remaining locations (orphaned)
  │
  ├─ 5. Re-sequence:
  │    ├─ Rebuild difficulty_map
  │    └─ Re-generate flow_map (version increment)
  │
  ├─ 6. GCS cleanup:
  │    ├─ Delete cid/originals/mid.*
  │    └─ Delete cid/frames/mid/ (all frame images)
  │
  ├─ 7. Delete material document itself
  │
  └─ 8. Update collection stats & progress
```

### DELETE Collection

```
DELETE /api/v1/collections/{cid}
  │
  ├─ 1. Delete all scoped index data:
  │    ├─ chunks, transcripts, extracted_frames, exercise_index
  │    ├─ topic_index, concept_graph, asset_index
  │    ├─ flow_map, difficulty_map
  │    └─ index_locks, merge_queue
  │
  ├─ 2. Delete all materials
  ├─ 3. Delete student_progress (tutor_v2 DB) for this collectionId
  ├─ 4. Delete GCS folder: cid/ (recursive)
  └─ 5. Delete collection document
```

---

## 12. Teaching Context — How the Tutor Sees BYO Content

### Activation
Frontend sends `collectionId` in the student profile JSON (within the context array). Chat route detects it via `_extract_collection_id()` and switches to BYO mode.

### Lean Context Snapshot (~600-800 tokens)
Built by `lean_context.py`, injected into the system prompt:

```
[Collection: Physics 101 — My Notes]
Subjects: classical mechanics, thermodynamics | 8 topics, 47 chunks, 15 exercises
collectionId: uuid-here

Sequence: Foundations (3 topics) → Dynamics (2 topics) → Energy (3 topics)

[Student Progress]
Sessions: 3 | Completed topics: 2
Current topic: Newton's Second Law (topicId: uuid)
Needs work: friction, circular_motion

[MQL Tools — Content Discovery]
  browse_topics()          — list all topics
  browse_topic(topicId)    — details for one topic
  ... (abbreviated reference)
```

### System Prompt Structure
```
TUTOR_SYSTEM_PROMPT (personality, pedagogy)
  + MQL_TOOLKIT_PROMPT (12 tools, teaching flow instructions)
  + TAGS_PROMPT (teaching tag syntax)
  + lean context snapshot
  + student profile
  + student model (private notes)
  + agent results (if any)
```

### Teaching Flow
1. **Session start**: Tutor calls `get_flow()` + `get_mastery()` → plans what to teach
2. **Per topic**: `browse_topic(topicId)` → `read_chunk(chunkId)` → teach with board/voice → `get_exercises(topicId)` → assess → `log_observation()`
3. **Student asks random question**: `search_content("their question")` (or `semantic_search`) → `read_chunk()` → answer grounded in their materials
4. **Crash course**: `get_flow()` + `difficulty_map` → tutor selects key topics → compressed teaching plan

---

## 13. Student Use Cases & Retrieval Paths

| Student Says | Retrieval Path | Works Today? |
|-------------|---------------|-------------|
| "Teach me my course" | `get_flow()` → sequential topic teaching | Yes |
| "Teach me from topic X" | `search_content("X")` or `browse_topics()` → `browse_topic()` → `read_chunk()` | Yes (keyword); Needs vector for fuzzy |
| "Explain this derivation" | `semantic_search("derivation of X")` → `read_chunk()` | **No** — needs vector search |
| "Assess me on uploaded exam papers" | `get_exercises(difficulty="advanced")` → assessment flow | Partially — depends on exercise extraction quality |
| "Prepare crash course, exam in 2 days" | `get_flow()` + `difficulty_map` → select key topics → compressed plan | Yes — tutor intelligence handles this |
| "What's in my collection?" | `browse_topics()` → overview | Yes |
| "Show me the diagram from lecture 3" | `get_assets(topicId, type="diagram")` → signed URL | Partially — needs signed URL endpoint |
| "I uploaded new notes, teach from those too" | Upload → pipeline → incremental merge → tutor picks up on next `browse_topics()` | Yes |
| "Delete that PDF I uploaded" | **DELETE material endpoint** → cascading cleanup | **No** — not implemented |
| "Can you search for something specific in my materials?" | `search_content(query)` or `grep_material(materialId, query)` | Yes (keyword) |

### Random Access Pattern (Student addresses things randomly)

The tutor handles random student queries through the MQL tools:

1. Student: "Hey, can you explain the thing about torque from that video I uploaded?"
2. Tutor: calls `search_content("torque")` → finds 3 chunks mentioning torque
3. Tutor: calls `read_chunk(best_match)` → gets full content
4. Tutor: teaches from the chunk content, draws on board, references video timestamp

With **vector search**, step 2 becomes much more robust — the student doesn't need to use the exact word "torque" (could say "the rotational force thing").

---

## 14. Frontend Integration Points

### What Needs to Be Built

1. **Enable BYO card** — Remove `if (cid === 'byo') return` guard in `app.js`
2. **Collection creation flow** — Name collection → upload materials → show progress
3. **Upload UI** — Drag-and-drop zone supporting PDF, images, text paste, YouTube URL paste
4. **Processing status** — Poll `GET /collections/{id}/status`, show per-material status
5. **Material list** — Browse uploaded materials with type icons, status badges
6. **Wire `collectionId`** — `buildContext()` must include `collectionId` in student profile when starting a BYO session
7. **Material management** — Delete materials, add more to existing collection
8. **Raw material viewer** — Signed URL access to view original PDFs, images, video frames

### Context Wiring (Critical Path)

In `app.js`, `buildContext()` currently sends:
```javascript
{ courseId, studentName, userEmail, teachingMode, ... }
```

For BYO, it must also send:
```javascript
{ collectionId: "uuid-of-active-collection", ... }
```

The chat route's `_extract_collection_id()` reads this and activates BYO mode.

---

## 15. External Dependencies & Cost Model

| Service | Used For | Cost Estimate |
|---------|----------|---------------|
| **Anthropic Claude Sonnet** | Topic detection, concept merge, flow map, chunking | ~$0.05-0.15 per material |
| **Anthropic Claude Haiku** | Classification, enrichment (per-chunk), exercises | ~$0.01-0.03 per material |
| **Claude Vision** | Frame classification, OCR | ~$0.01-0.05 per video (depends on frame count) |
| **YouTube Captions API** | Free transcription | Free |
| **ElevenLabs STT** (proposed) | Transcription fallback, non-YouTube video | ~$0.01/min audio |
| **OpenAI Embeddings** (proposed) | Vector embeddings for chunks | ~$0.001 per material (negligible) |
| **Google Cloud Storage** | Original files, frames, transcripts | ~$0.02/GB/month |
| **MongoDB Atlas** | All structured data + vector search | Existing infrastructure |

**Per-material cost estimate**: ~$0.05-0.25 depending on size and type.
**Per-collection cost estimate** (10 materials): ~$0.50-2.50

---

## 16. Production Concerns

### Rate Limiting
- Upload endpoint: Rate limit per user (e.g., 10 uploads/minute, 100 uploads/day)
- Pipeline: Max concurrent background tasks per collection (prevent resource exhaustion)

### File Size Limits
- PDF: 50MB (current)
- Video file (proposed): 500MB
- Image: 10MB
- Text: 1MB
- Total collection: 2GB

### Error Recovery
- Each material processes independently — one failure doesn't block others
- Failed materials can be retried (re-upload)
- Pipeline status tracking at each stage — visible to user via status endpoint
- Quality gate prevents garbage-in-garbage-out

### Monitoring
- Pipeline processing time per material (alert if > 5 minutes for text, > 15 for video)
- LLM call failures (retry with exponential backoff)
- GCS upload/download failures
- Index merge lock contention (alert if queue grows)

### Security
- All GCS access via signed URLs (60-min expiry)
- User-scoped collection access (userId check on all endpoints)
- File upload validation (magic bytes check for PDF, image; no executable uploads)
- Transcription content stays server-side (no API keys on frontend)

---

## 17. Implementation Status & Gaps

### Implemented (Backend)

| Component | Files | Notes |
|-----------|-------|-------|
| Collection CRUD | `ingestion.py` | Create, list, get, status |
| Material upload (PDF, YouTube, text) | `ingestion.py`, `orchestrator.py` | Multipart + JSON |
| Full pipeline (10 stages) | `orchestrator.py`, `extractors/*`, `processors/*`, `transcribers/*` | End-to-end |
| Incremental merge with locking | `index_builder.py` | MongoDB locks + queue |
| Flow map generation | `sequencer.py` | Versioned, re-generated on merge |
| MQL tools (12) | `mql.py`, `tools/__init__.py` | Full implementation |
| Lean context builder | `lean_context.py` | ~600 token snapshot |
| BYO tutor prompt | `toolkit.py` | MQL teaching instructions |
| Chat route BYO branch | `chat.py` | Activated by `collectionId` |
| GCS storage | `gcs.py` | Upload, download, signed URL, delete |
| MongoDB indexes | `byo_indexes.py` | 11 collections indexed |

### Not Implemented (Gaps)

| Gap | Priority | Estimated Effort |
|-----|----------|-----------------|
| **Material deletion endpoint + cascading cleanup** | P0 | 1-2 days |
| **Collection deletion endpoint** | P0 | 0.5 day |
| **Frontend: Upload UI + collection management** | P0 | 3-4 days |
| **Frontend: Wire `collectionId` into context** | P0 | 0.5 day |
| **Image source type** (upload → OCR → chunk) | P1 | 1-2 days |
| **Vector embeddings + semantic search** | P1 | 2-3 days |
| **Signed URL endpoint** for raw material access | P1 | 0.5 day |
| **ElevenLabs STT adapter** (replace Deepgram) | P1 | 1 day |
| **Video file upload** (MP4/MOV → GCS → transcribe → frames) | P2 | 2-3 days |
| **PPTX support** | P3 | 1-2 days |
| **DOCX support** | P3 | 0.5 day |

### Recommended Implementation Order

1. **P0 block** (minimum viable): Deletion + Frontend upload + Context wiring → BYO is usable end-to-end
2. **P1 block** (quality): Image upload + Vector search + Signed URLs + ElevenLabs STT → handles real student workflows
3. **P2 block** (completeness): Video files + PPTX/DOCX → handles all common file types
