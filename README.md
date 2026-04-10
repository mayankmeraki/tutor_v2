# Euler Tutor

AI tutoring platform with voice-mode teaching, interactive chalkboard, and real-time code execution. Built on Claude (via OpenRouter/Anthropic) with WebSocket streaming, server-side TTS, and a DOM-based board renderer.

## Quick Start

```bash
# 1. Clone
git clone git@github.com:seekcapacity/euler_tutor.git
cd euler_tutor

# 2. Set up backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 3. Create .env (see Environment Variables below)
cp .env.example .env
# Fill in your API keys

# 4. Start the server
cd ..
./start.sh
# Or manually: uvicorn app.main:app --host 0.0.0.0 --port 3001 --app-dir ./backend

# 5. Open in browser
open http://localhost:3001
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│ Browser                                             │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐ │
│  │ app.js   │  │ board/   │  │ Pyodide (Python)  │ │
│  │ (voice,  │  │ bundle.js│  │ (code execution   │ │
│  │  WS,     │  │ (render) │  │  in browser)      │ │
│  │  state)  │  │          │  │                   │ │
│  └────┬─────┘  └──────────┘  └───────────────────┘ │
│       │ WebSocket                                   │
└───────┼─────────────────────────────────────────────┘
        │
┌───────┼─────────────────────────────────────────────┐
│ Backend (FastAPI, port 3001)                        │
│       │                                             │
│  ┌────┴──────────────────────────────────────────┐  │
│  │ Teaching Pipeline (WebSocket)                 │  │
│  │  ├─ Tutor Agent (Opus) — teaches via voice    │  │
│  │  ├─ Planner Agent (Sonnet) — creates plans    │  │
│  │  ├─ Assessment Agent — checkpoints            │  │
│  │  └─ Enrichment Agent (Haiku) — pre-fetches    │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  ┌─────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ MongoDB │  │ Postgres │  │ External APIs    │   │
│  │ (users, │  │ (courses,│  │ • OpenRouter/    │   │
│  │  notes, │  │  content)│  │   Anthropic LLM  │   │
│  │  state) │  │          │  │ • ElevenLabs TTS │   │
│  └─────────┘  └──────────┘  │ • GCS storage    │   │
│                              └──────────────────┘   │
└─────────────────────────────────────────────────────┘
```

## Environment Variables

Create `backend/.env` with the following:

### Required

| Variable | Description |
|----------|-------------|
| `MOCKUP_JWT_SECRET` | JWT signing secret (any random string, e.g. `openssl rand -hex 32`) |
| `OPENROUTER_API_KEY` | OpenRouter API key ([openrouter.ai/keys](https://openrouter.ai/keys)) |
| `MONGODB_URI` | MongoDB connection string (e.g. `mongodb+srv://user:pass@cluster.mongodb.net/capacity`) |

### Recommended

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openrouter` | `openrouter` or `anthropic` |
| `TUTOR_MODEL` | `anthropic/claude-opus-4-6` | Model for teaching (use Opus for quality) |
| `ELEVENLABS_API_KEY` | — | ElevenLabs TTS key (voice mode won't work without this) |
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5433` | PostgreSQL port |
| `DB_NAME` | `capacity` | PostgreSQL database name |
| `DB_USER` | `capacity_service_user` | PostgreSQL user |
| `DB_PASSWORD` | — | PostgreSQL password |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Direct Anthropic key (fallback if not using OpenRouter) |
| `PORT` | `3001` | Server port |
| `PLANNING_MODEL` | `anthropic/claude-sonnet-4-6` | Model for planning agent |
| `RESEARCH_MODEL` | `anthropic/claude-haiku-4.5` | Model for research/enrichment |
| `MODEL_EMBEDDING` | `openai/text-embedding-3-small` | Embedding model |
| `SEARCHAPI_KEY` | — | SearchAPI key for image search |
| `RESEND_API_KEY` | — | Resend email service key |
| `CORS_ORIGINS` | localhost | Comma-separated production CORS origins |
| `SESSION_ATTACHMENTS_BUCKET` | `capacity-session-attachments` | GCS bucket for uploads |

### Example `.env`

```bash
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-your-key-here
TUTOR_MODEL=anthropic/claude-opus-4-6
MOCKUP_JWT_SECRET=your-random-secret-here-at-least-32-chars
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/capacity
ELEVENLABS_API_KEY=sk_your-elevenlabs-key
DB_HOST=localhost
DB_PORT=5433
DB_NAME=capacity
DB_USER=capacity_service_user
DB_PASSWORD=your-db-password
PORT=3001
```

## Project Structure

```
backend/
  app/
    main.py                    # FastAPI app, lifespan, static file serving
    core/
      config.py                # Settings (all env vars)
      database.py              # PostgreSQL (SQLAlchemy async)
      mongodb.py               # MongoDB (Motor async)
      llm/                     # LLM providers (Anthropic + OpenRouter)
    api/routes/                # REST + WebSocket endpoints
    agents/
      session.py               # Session orchestration
      agent_runtime.py         # Sub-agent spawning (planner, assessment, etc.)
      prompts/                 # All prompt engineering
        voice/                 # Voice mode: board commands, scene structure
        sections/              # Pedagogy, execution, calibration, adaptation
        subjects/              # Subject-specific guidance (physics, CS, bio, etc.)
        assessment/            # Assessment checkpoint prompts
    services/
      teaching/
        pipeline.py            # Voice beat streaming pipeline
        tts_service.py         # ElevenLabs TTS proxy
      knowledge/               # Student model + concept mastery
    tools/                     # LLM tool definitions + executors
      schemas/                 # Tool JSON schemas (tutor, delegation, assessment)
      web_search.py            # DuckDuckGo search (fallback for Anthropic)
  tests/                       # pytest test suite
  pyproject.toml               # Python >=3.11, all dependencies

frontend/
  index.html                   # Landing page + SPA shell
  app.js                       # Main app (~19K lines): WS, voice bar, state, board
  styles.css                   # Global styles
  router.js                    # Client-side routing
  board/
    bundle.js                  # Board renderer: all draw commands, animations, code runner
    styles.css                 # Board-specific styles (chalkboard palette)
    text-animator.js           # Char-by-char text animation
    placement.js               # Layout placement engine
    state.js                   # Board state management
    commands.js                # Source module (parallel to bundle.js)
    animation.js               # p5.js animation helper
  tests/                       # Playwright E2E tests

deploy.sh                      # GCP Cloud Run deployment
Dockerfile                     # Python 3.11 + backend + frontend
cloudbuild.yaml                # GCP Cloud Build config
```

## Board Commands

The board renderer (`frontend/board/bundle.js`) supports these draw commands, emitted by the tutor via `<vb draw='...' say="..." />` voice beats:

### Layout blocks (prefer these)
| Command | Purpose |
|---------|---------|
| `split` | Thing left + meaning right (equations, terms, code annotations) |
| `flow` / `flow-add` | Process chain with glowing dots (biology, algorithms, pipelines) |
| `diff` | Before/after (mode: `fix` for corrections, `compare` for side-by-side) |
| `question-block` | Centered question with context + hint (4 random visual styles) |

### Content primitives
| Command | Purpose |
|---------|---------|
| `text` / `h1` / `h2` / `h3` / `note` | Text at various sizes. KaTeX auto-detection for `$...$` LaTeX. |
| `equation` | KaTeX-rendered math with note annotation |
| `step` | Numbered step in a sequence |
| `check` / `cross` | ✓ / ✗ markers |
| `callout` | Emphasis with left accent (gold/red/cyan). 3 random visual styles. |
| `list` | Bulleted or numbered list |
| `code` | Syntax-highlighted code block. `editable:true` for worksheets, `runnable:true` for Python execution (Pyodide). |

### Visual
| Command | Purpose |
|---------|---------|
| `animation` | p5.js sketch (self-contained figure with title + legend) |
| `figure` | Animation + narration column (beat-synced key points on the right) |
| `mermaid` | Mermaid.js diagrams (flowcharts, state diagrams) |

### Editing
| Command | Purpose |
|---------|---------|
| `update` | Update existing element by id (works for text, code, split) |
| `run` | Execute code in a runnable code block (Pyodide) |
| `code-highlight` | Highlight specific lines in a code block |
| `connect` | Draw arrow between two elements |
| `strikeout` / `delete` / `clone` | Element modifications |

## Running Tests

### Backend
```bash
cd backend
pip install pytest pytest-asyncio httpx
pytest tests/
```

### Frontend (Playwright)
```bash
cd frontend/tests
npm install
npx playwright install
npm test                # All tests
npm run test:headed     # With visible browser
npm run test:auth       # Auth tests only
npm run test:session    # Session tests only
```

## Deployment

Deploys to GCP Cloud Run via Cloud Build:

```bash
./deploy.sh              # Uses git SHA as tag
./deploy.sh --tag v1.0   # Custom tag
```

**GCP setup:**
- Project: `capacity-platform-dev`
- Service: `tutor-stage`
- Region: `us-central1`
- Secrets managed in GCP Secret Manager

**Cloud Run config:**
- Memory: 1Gi, CPU: 1
- Concurrency: 80, Max instances: 5
- Scales to zero when idle
- VPC connected for Cloud SQL access

## Key Design Decisions

- **Voice-first**: Teaching is delivered via TTS with synchronized board drawing. Text mode exists but voice is the default.
- **Opus for teaching**: Only Claude Opus is used for the tutor agent. Sonnet/Haiku are used for background agents (planning, enrichment, research). Opus produces significantly better teaching quality.
- **No x,y coordinates for content**: Board layout is controlled by semantic placement (`below`, `row-start`/`row-next`, `figure:<id>`). The LLM picks WHAT to show, the renderer handles WHERE.
- **Eager execution**: Planner runs in background while the tutor starts teaching immediately. No waiting for plans. Content summaries baked into plans so the tutor doesn't need tool calls for the first 3 turns.
- **Code state flows via context, not tools**: Interactive code runner state (edits, run output, test results) is shipped to the tutor via the existing context payload on every message. No tool calls needed.
- **OpenRouter web search**: Uses OpenRouter's native `openrouter:web_search` server tool (Exa-powered) instead of custom DuckDuckGo scraping. The model decides when to search.
