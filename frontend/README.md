# Capacity Frontend (React rewrite)

Vite + React 18 + TypeScript + React Router 6 + TanStack Query + Zustand + Tailwind.

This replaces the previous static `frontend/` (now preserved as `frontend-legacy/` while the
rewrite is in progress).

## Quick start

```bash
# Install
npm install

# Dev server (Vite on :5173, proxies /api, /ws, /rendered to FastAPI on :4010)
npm run dev

# Production build (outputs to dist/)
npm run build

# Typecheck only
npm run typecheck

# Lint
npm run lint

# Unit tests
npm run test
```

The FastAPI backend serves `frontend/dist/` automatically when `dist/index.html` exists
(see `backend/app/main.py` `FRONTEND_DIR` selection logic).

For dev, run the backend on :4010 (or set `VITE_BACKEND_TARGET=http://localhost:PORT`)
and Vite will proxy.

## Layout

```
src/
  routes/                  one file per route (mirrors frontend-legacy/router.js)
  features/
    auth/                  JWT, Google GIS, ProtectedRoute
    config/                /api/config provider
    board/                 native React BoardEngine
      engine/              queue, scene stack, placement, registry
      commands/            text, latex, animation, mermaid, chart, scene3d, ds, code, assess, diagram
    sd-canvas/             native React Fabric system-design canvas
    voice/                 mic, scribe WS, TTS playback, voice bar
    tutor/                 ws_chat hook + protocol
    paths/                 wizard, planner SSE, refine SSE, node ops
  components/
    layout/                AppShell, TopNav
    ui/                    Button, Input, Card, Modal, Toast, Tabs, Spinner
    effects/               DashBg animated background
  lib/
    api/                   typed clients per backend router
    ws/                    useWebSocket + chat/scribe protocol types
    sse/                   useEventSource + streamingPost (for SSE-via-POST)
  stores/                  Zustand: auth
  styles/                  globals.css with Tailwind + design tokens
public/
  fonts/                   Bright Chalk, ChalkBoard, CoalhandLuke (board fonts)
```

## Architecture notes

- **Auth**: token + user persisted in `localStorage` under `mockup_auth` (Zustand
  `persist` middleware).
- **API**: every request is auto-Bearer-tokened; 401 clears auth and redirects to
  `/login`.
- **Board engine**: imperative DOM/SVG core (TypeScript port of
  `frontend-legacy/board/`) wrapped in a thin `<Board>` React component for parity
  with the legacy command queue. Subsystems lazy-import their heavy deps
  (KaTeX, mermaid, vega-embed, three.js) so the initial bundle stays small.
- **Realtime**: `useWebSocket` for `/ws/chat` + `/ws/scribe`, `useEventSource` for
  `/api/events/:id`, `streamingPost` for SSE-via-POST endpoints
  (`/api/v1/paths/plan`, `/api/v1/paths/{id}/refine`).
- **Routing**: all 11 legacy routes preserved (`/`, `/login`, `/home`,
  `/dashboard`, `/tutor`, `/session/:id`, `/for-business`, `/dsa`, `/dsa/:slug`,
  `/mock`) plus `/paths`, `/byo`, `/artifacts`.
