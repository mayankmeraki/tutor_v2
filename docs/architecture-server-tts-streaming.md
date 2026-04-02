# Architecture: Server-Side TTS + WebSocket Streaming

**Branch:** `refactor/be_stream`
**Status:** Design complete, implementation not started
**Date:** 2026-04-02

---

## 1. Problem Statement

The current client-side TTS architecture is unreliable in production:

- Browser calls ElevenLabs TTS per voice beat — fails silently under load
- Audio context gets throttled/suspended when tab is backgrounded
- Client manages complex voice scene parsing, TTS prefetching, retry logic, and audio playback (~2000 lines)
- ElevenLabs API key is exposed to the client (proxied, but still client-initiated)
- When TTS fails, the board draw + audio sync breaks entirely
- Interrupting a stream involves race conditions between HTTP fetch cancellation, audio context teardown, and beat queue flushing

**Goal:** Move TTS to the server. Stream text + audio over a single WebSocket. Simplify the client to a beat queue player.

---

## 2. Current Architecture (What We're Replacing)

### Server (SSE)

```
POST /api/chat → StreamingResponse (text/event-stream)

generate() async generator:
  1. Session lookup/create
  2. Agent runtime setup (planner, delegator, assessor)
  3. LLM streaming loop (Anthropic claude_messages)
  4. Tool call handling (get_section_content, search, etc.)
  5. Yield SSE events: TEXT_DELTA, TOOL_USE, PLAN_UPDATE, etc.
```

**Key files:**
- `backend/app/api/routes/chat.py` — `chat()` at line 1633, `generate()` at line 1709
- `backend/app/main.py` — `/api/tts` proxy at line 172

**SSE event format:**
```
data: {"type": "TEXT_DELTA", "text": "Let's look at..."}
data: {"type": "PLAN_UPDATE", "sections": [...]}
data: {"type": "TOOL_USE", "name": "get_section_content", ...}
data: {"type": "RUN_ERROR", "message": "..."}
data: {"type": "DONE"}
```

**TTS proxy (`/api/tts`):**
- Client POSTs `{text, voice_id}` → server calls ElevenLabs streaming API → pipes audio/mpeg back
- Model: `eleven_turbo_v2_5`
- Voice: `UgBBYS2sOqTuMpoF3BR0`
- Voice settings: `stability: 0.55, similarity_boost: 0.75, style: 0.2`
- Latency optimization: level 4
- Max text: 500 chars (truncated to 490 client-side)

### Client (SSE + TTS)

```
streamADK() → fetch(POST /api/chat) → ReadableStream
  → handleSSEEvent() → parse teaching tags
  → _eagerBeatWatcher() → parse <vb /> tags as they stream
  → _eagerExecutorLoop() → for each beat:
      → executeDraw() → BoardEngine commands
      → executeSay() → voiceSpeak() → fetch(/api/tts) → AudioContext.play()
      → voiceBeatGap() → inter-beat pause
```

**Key files and functions:**
- `frontend/app.js`:
  - `streamADK()` — line 1235: main streaming entry point
  - `handleSSEEvent()` — line ~1500: SSE event dispatcher
  - `_eagerBeatWatcher()` — line 15964: parses `<vb />` tags from streaming text
  - `_eagerExecutorLoop()` — line 16093: sequential beat executor
  - `_eagerExecBeat()` — line 16168: single beat execution (draw + say + gap)
  - `voiceFetchTTS()` — line 15597: prefetch TTS via /api/tts
  - `voiceSpeak()` — line 15613: play audio via AudioContext
  - `stopAll()` — line 17077: nuclear stop (kills everything)
  - `_eager` object — line 15946: eager beat parsing state
  - `_streamGeneration` — generation counter for stale event filtering

**Voice beat format (LLM output):**
```xml
<teaching-voice-scene title="The Schrödinger Equation">
  <vb say="Let's start with the equation"
      draw='{"cmd":"text","text":"iℏ ∂ψ/∂t = Ĥψ","x":50,"y":20}'
      cursor="draw" />
  <vb say="The left side is about change"
      draw='{"cmd":"note","text":"LEFT side: iℏ ∂ψ/∂t","x":60,"y":40,"color":"#fbbf24"}'
      cursor="point" />
  <vb say="What does this tell you?"
      question="true" />
</teaching-voice-scene>
```

**Interrupt flow (current):**
1. `stopAll()` sets `state._stopRequested = true`
2. Cancels `state._streamReader` (HTTP ReadableStream)
3. Destroys AudioContext + all audio elements
4. Sets `_eager.done = true`, clears queue
5. Cancels BoardEngine
6. Saves partial message text
7. Marks `state.isStreaming = false`

---

## 3. New Architecture

### Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        CLIENT                                │
│                                                              │
│  WebSocket ←──── JSON frames (text, board, control)          │
│  connection ←── Binary frames (audio chunks, beat-tagged)    │
│                                                              │
│  Beat Queue Player:                                          │
│    - Buffer events by beat number                            │
│    - Play audio + render board/text per beat                 │
│    - AUDIO_SKIP → render without waiting for audio           │
│    - Generation counter → drop stale frames on interrupt     │
└──────────────────────┬──────────────────────────────────────┘
                       │ WebSocket
                       │
┌──────────────────────┴──────────────────────────────────────┐
│                        SERVER                                │
│                                                              │
│  WebSocket Endpoint (/ws/chat)                               │
│       │                                                      │
│  SessionRouter (per connection)                              │
│       │                                                      │
│  TurnQueue (per turn — isolated, self-cleaning)              │
│       │                                                      │
│   ┌───┴──────────┐                                           │
│   │  Producers:  │                                           │
│   │  - LLM stream + beat parser → TEXT, BOARD_DRAW events   │
│   │  - TTS pipeline → binary AUDIO frames                   │
│   │  - Tool executor → TOOL_RESULT events                   │
│   │  - Agent runtime → PLAN_UPDATE, ASSESSMENT events       │
│   └──────────────┘                                           │
└─────────────────────────────────────────────────────────────┘
```

### 3.1 Server Components

#### WebSocket Endpoint

**File:** `backend/app/api/routes/ws_chat.py` (new)

```python
@app.websocket("/ws/chat")
async def ws_chat(ws: WebSocket):
    await ws.accept()
    user = authenticate_ws(ws)  # extract JWT from query param or first message
    router = SessionRouter(ws)
    
    try:
        while True:
            msg = await ws.receive_json()
            
            if msg["type"] == "MESSAGE":
                await router.handle_message(msg["text"], msg["context"], msg.get("sessionId"), msg.get("isSessionStart"))
            elif msg["type"] == "INTERRUPT":
                await router.handle_interrupt()
            elif msg["type"] == "CANCEL":
                await router.handle_cancel()
            elif msg["type"] == "VOICE_MODE":
                router.voice_enabled = msg["enabled"]
    except WebSocketDisconnect:
        await router.cleanup()
```

#### TurnQueue

**File:** `backend/app/services/turn_queue.py` (new)

Each turn is an isolated unit. When interrupted, the entire turn is killed — no partial cleanup.

```python
class TurnQueue:
    turn_id: str
    generation: int
    queue: asyncio.Queue        # events to send to client
    cancelled: asyncio.Event    # set on interrupt/cancel
    tasks: list[asyncio.Task]   # LLM + TTS tasks (cancelled on cleanup)
    
    def put(event: dict | bytes)    # add event (no-op if cancelled)
    async def drain(ws: WebSocket)  # consume queue → send to client
    async def cleanup()             # cancel all tasks, flush queue
```

**Critical:** `cleanup()` must:
1. Set `cancelled` event
2. Cancel all asyncio tasks
3. Drain the queue (so blocked `put()` calls don't hang)

#### SessionRouter

**File:** `backend/app/services/session_router.py` (new)

```python
class SessionRouter:
    ws: WebSocket
    active_turn: TurnQueue | None
    generation: int = 0           # increments on each turn
    voice_enabled: bool = True
    
    async def handle_message(text, context, session_id, is_start):
        # Kill previous turn if any
        if self.active_turn:
            await self.active_turn.cleanup()
        
        self.generation += 1
        turn = TurnQueue(turn_id=uuid4().hex[:8], generation=self.generation)
        self.active_turn = turn
        
        # Start producers (they put events into turn.queue)
        task = asyncio.create_task(self.run_turn(turn, text, context, session_id, is_start))
        turn.tasks.append(task)
        
        # Drain to WebSocket (blocks until turn complete or cancelled)
        await turn.drain(self.ws)
    
    async def handle_interrupt():
        if self.active_turn:
            await self.active_turn.cleanup()
            self.active_turn = None
        await self.ws.send_json({"type": "INTERRUPTED", "gen": self.generation})
    
    async def handle_cancel():
        if self.active_turn:
            await self.active_turn.cleanup()
            self.active_turn = None
        await self.ws.send_json({"type": "CANCELLED", "gen": self.generation})
```

#### LLM + Beat Parser Producer

**Reuses existing `generate()` logic from `chat.py`**, but instead of yielding SSE strings, puts structured events into the TurnQueue.

The beat parser extracts `<vb />` tags from the streaming text and emits per-beat events.

```python
async def run_turn(self, turn, text, context, session_id, is_start):
    # ... existing session setup, context extraction, prompt building ...
    
    beat_num = 0
    text_buffer = ""
    
    async for chunk in llm_stream(tutor_prompt, claude_messages, tools):
        if turn.cancelled.is_set():
            break
        
        if chunk.type == "text_delta":
            text_buffer += chunk.text
            
            # Parse completed <vb /> tags
            while has_complete_vb_tag(text_buffer):
                beat_num += 1
                beat = extract_next_vb(text_buffer)
                text_buffer = remaining_text(text_buffer)
                
                # Emit board draw immediately (don't wait for audio)
                if beat.draw:
                    turn.put({"type": "BOARD_DRAW", "beat": beat_num, "gen": self.generation, "content": beat.draw})
                
                # Emit text
                if beat.say:
                    turn.put({"type": "TEXT", "beat": beat_num, "gen": self.generation, "text": beat.say})
                
                # TTS (async — fire and forget into queue)
                if beat.say and self.voice_enabled:
                    tts_task = asyncio.create_task(
                        self.produce_audio(turn, beat_num, beat.say)
                    )
                    turn.tasks.append(tts_task)
                elif beat.say:
                    turn.put({"type": "AUDIO_SKIP", "beat": beat_num, "gen": self.generation})
                
                # Question beat
                if beat.question:
                    turn.put({"type": "QUESTION", "beat": beat_num, "gen": self.generation, "text": beat.say})
        
        elif chunk.type == "tool_use":
            # ... handle tool calls same as current generate() ...
            turn.put({"type": "TOOL_RESULT", "gen": self.generation, ...})
    
    turn.put({"type": "DONE", "gen": self.generation})
    turn.put(None)  # sentinel to end drain()
```

#### TTS Producer

```python
async def produce_audio(self, turn: TurnQueue, beat_num: int, text: str):
    """Call ElevenLabs streaming, put audio bytes into turn queue."""
    if turn.cancelled.is_set():
        return
    
    clean = voice_clean_text(text)[:490]
    if not clean or len(clean) < 3:
        turn.put({"type": "AUDIO_SKIP", "beat": beat_num, "gen": self.generation})
        return
    
    try:
        audio_bytes = await asyncio.wait_for(
            elevenlabs_tts(clean), timeout=5.0
        )
        if turn.cancelled.is_set():
            return
        # Binary frame: [2 bytes beat_num] [4 bytes generation] [audio bytes]
        header = struct.pack(">HI", beat_num, self.generation)
        turn.put(header + audio_bytes)
    
    except (asyncio.TimeoutError, Exception) as e:
        log.warning("TTS failed for beat %d: %s", beat_num, e)
        turn.put({"type": "AUDIO_SKIP", "beat": beat_num, "gen": self.generation})
```

**ElevenLabs call (server-side):**
```python
async def elevenlabs_tts(text: str) -> bytes:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream",
            headers={
                "xi-api-key": settings.ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json={
                "text": text,
                "model_id": "eleven_turbo_v2_5",
                "voice_settings": {"stability": 0.55, "similarity_boost": 0.75, "style": 0.2},
                "optimize_streaming_latency": 4,
            },
        )
        if resp.status_code != 200:
            raise Exception(f"ElevenLabs {resp.status_code}")
        return resp.content
```

### 3.2 Client Components

#### WebSocket Connection Manager

**Replace in:** `frontend/app.js` — replaces `streamADK()` fetch-based SSE

```javascript
let ws = null;
let activeGeneration = 0;
let currentBeat = 0;
const beats = {};  // beat_num → { text, boards[], audio, skip }

function connectWS() {
    const token = AuthManager.getToken();
    ws = new WebSocket(`ws://${location.host}/ws/chat?token=${token}`);
    ws.binaryType = 'arraybuffer';
    
    ws.onmessage = onWSMessage;
    ws.onclose = () => { setTimeout(connectWS, 2000); };  // reconnect
}

function sendMessage(text, context, sessionId, isSessionStart) {
    state.isStreaming = true;
    currentBeat = 0;
    beats = {};
    setVoiceBarState('thinking');
    
    ws.send(JSON.stringify({
        type: "MESSAGE",
        text, context, sessionId, isSessionStart
    }));
}

function interrupt() {
    // Immediate client-side cleanup (don't wait for server)
    stopAudioPlayback();
    activeGeneration++;
    currentBeat = 0;
    beats = {};
    
    ws.send(JSON.stringify({ type: "INTERRUPT" }));
}

function cancel() {
    stopAudioPlayback();
    activeGeneration++;
    currentBeat = 0;
    beats = {};
    state.isStreaming = false;
    setVoiceBarState('idle');
    
    ws.send(JSON.stringify({ type: "CANCEL" }));
}
```

#### Beat Queue Player

```javascript
function onWSMessage(msg) {
    if (msg.data instanceof ArrayBuffer) {
        // Binary: audio chunk
        const view = new DataView(msg.data);
        const beatNum = view.getUint16(0);
        const gen = view.getUint32(2);
        if (gen !== activeGeneration) return;  // stale
        
        beats[beatNum] = beats[beatNum] || {};
        beats[beatNum].audio = msg.data.slice(6);
        tryPlayNext();
        return;
    }
    
    const evt = JSON.parse(msg.data);
    
    // Control events (no generation check)
    if (evt.type === 'INTERRUPTED' || evt.type === 'CANCELLED') {
        // Server confirmed — client already cleaned up in interrupt()/cancel()
        state.isStreaming = false;
        setVoiceBarState('idle');
        return;
    }
    
    // Stale check
    if (evt.gen !== undefined && evt.gen !== activeGeneration) return;
    
    switch (evt.type) {
        case 'TEXT':
            beats[evt.beat] = beats[evt.beat] || {};
            beats[evt.beat].text = evt.text;
            break;
        
        case 'BOARD_DRAW':
            // Board draws render IMMEDIATELY — don't wait for audio
            executeBoardDraw(evt.content);
            break;
        
        case 'AUDIO_SKIP':
            beats[evt.beat] = beats[evt.beat] || {};
            beats[evt.beat].skip = true;
            tryPlayNext();
            break;
        
        case 'QUESTION':
            voiceShowBoardQuestion(evt.text);
            break;
        
        case 'PLAN_UPDATE':
            updatePlanSidebar(evt);
            break;
        
        case 'TOOL_RESULT':
            // Handle same as current handleSSEEvent
            break;
        
        case 'THINKING':
            showThinkingIndicator();
            break;
        
        case 'DONE':
            state.isStreaming = false;
            setVoiceBarState('idle');
            break;
    }
}

function tryPlayNext() {
    const b = beats[currentBeat];
    if (!b) return;
    
    if (b.skip) {
        // No audio for this beat — render subtitle and move on
        if (b.text) voiceShowSubtitle(b.text);
        currentBeat++;
        tryPlayNext();
        return;
    }
    
    if (!b.audio) return;  // waiting for audio to arrive
    
    // Play audio
    const blob = new Blob([b.audio], { type: 'audio/mpeg' });
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.playbackRate = state.playbackSpeed || 1;
    state._currentAudio = audio;
    
    audio.onended = () => {
        URL.revokeObjectURL(url);
        currentBeat++;
        tryPlayNext();
    };
    
    audio.play().catch(() => {
        // Autoplay blocked — skip
        currentBeat++;
        tryPlayNext();
    });
    
    // Show subtitle while audio plays
    if (b.text) voiceShowSubtitle(b.text);
}
```

#### Pause / Resume (client-only)

```javascript
function pausePlayback() {
    state.paused = true;
    if (state._currentAudio) state._currentAudio.pause();
    setVoiceBarState('paused');
}

function resumePlayback() {
    state.paused = false;
    if (state._currentAudio) state._currentAudio.play();
    setVoiceBarState('speaking');
}
```

#### Speed Control (client-only)

```javascript
function setSpeed(rate) {
    state.playbackSpeed = rate;
    if (state._currentAudio) state._currentAudio.playbackRate = rate;
}
```

---

## 4. WebSocket Protocol

### Client → Server

| Message | Fields | When |
|---------|--------|------|
| `MESSAGE` | `{type, text, context[], sessionId, isSessionStart}` | Student sends a message |
| `INTERRUPT` | `{type: "INTERRUPT"}` | Student types while tutor speaking |
| `CANCEL` | `{type: "CANCEL"}` | Student clicks stop, no follow-up |
| `VOICE_MODE` | `{type: "VOICE_MODE", enabled: bool}` | Toggle TTS on/off |

### Server → Client (JSON frames)

| Message | Fields | When |
|---------|--------|------|
| `TEXT` | `{type, beat, gen, text}` | Spoken text for a beat |
| `BOARD_DRAW` | `{type, beat, gen, content}` | Board draw command (render immediately) |
| `AUDIO_SKIP` | `{type, beat, gen}` | TTS failed — render beat without audio |
| `QUESTION` | `{type, beat, gen, text}` | Beat is a question — show input |
| `THINKING` | `{type, gen}` | Tool call in progress |
| `PLAN_UPDATE` | `{type, gen, sections[]}` | Plan sidebar update |
| `TOOL_RESULT` | `{type, gen, name, result}` | Tool execution result |
| `ASSESSMENT` | `{type, gen, ...}` | Assessment events |
| `VIDEO_RESUME` | `{type, gen}` | Resume video playback |
| `VIDEO_SEEK` | `{type, gen, timestamp}` | Seek video |
| `INTERRUPTED` | `{type, gen}` | Confirm interrupt processed |
| `CANCELLED` | `{type, gen}` | Confirm cancel processed |
| `DONE` | `{type, gen}` | Turn complete |
| `RUN_ERROR` | `{type, message}` | Fatal error |

### Server → Client (Binary frames)

```
[2 bytes: beat number (uint16 big-endian)]
[4 bytes: generation (uint32 big-endian)]
[remaining: audio/mpeg bytes]
```

---

## 5. Edge Cases & Failure Handling

### 5.1 TTS Failure (CRITICAL — must handle from day 1)

**Scenario:** ElevenLabs times out or returns error for a beat.

**Risk:** Client waiting for audio that never arrives → UI freezes.

**Server fix:**
```python
try:
    audio = await asyncio.wait_for(elevenlabs_tts(text), timeout=5.0)
    turn.put(header + audio)
except:
    turn.put({"type": "AUDIO_SKIP", "beat": beat_num, "gen": gen})
```

**Client fix:** `AUDIO_SKIP` → render beat without audio, advance to next beat.

**Belt-and-suspenders (client):** If no audio AND no AUDIO_SKIP arrives for the current beat within 4 seconds, auto-skip:
```javascript
// In tryPlayNext(), when waiting for audio:
if (!b.audio && !b.skip) {
    if (!b._timeout) {
        b._timeout = setTimeout(() => {
            b.skip = true;
            tryPlayNext();
        }, 4000);
    }
    return;
}
```

### 5.2 Stale Frames After Interrupt

**Scenario:** Server sent 5 events before INTERRUPT was processed. Those 5 events are in the TCP pipe.

**Why TurnQueue doesn't fully solve this:** The queue is dead, but events already `send()`-ed are in the OS TCP buffer.

**Fix:** `generation` counter on every event. Client increments `activeGeneration` immediately on interrupt. Stale frames have old generation → dropped silently.

**Key rule:** Client does NOT wait for INTERRUPTED confirmation to clean up. It acts immediately on user action.

### 5.3 WebSocket Connection Drop

**Scenario:** WiFi hiccup, laptop sleep, tab backgrounded for too long.

**Server:** Detects `WebSocketDisconnect`, calls `router.cleanup()` which kills the active TurnQueue.

**Client:** `ws.onclose` triggers reconnect with exponential backoff:
```javascript
ws.onclose = (e) => {
    stopAudioPlayback();
    state.isStreaming = false;
    setTimeout(connectWS, Math.min(2000 * Math.pow(2, retryCount), 30000));
    retryCount++;
};
```

**On reconnect:** Client sends session ID. Server restores session state from memory/DB. No attempt to resume mid-turn — fresh start from next message.

### 5.4 Long Tool Calls (2-5 seconds)

**Scenario:** `get_section_content` or `web_search` takes time. No beats generated during wait.

**Risk:** Audio for current beat finishes. Silence. Student thinks it's broken.

**Fix:** Server sends `{type: "THINKING"}` when tool call starts. Client shows subtle indicator. When tool resolves and text resumes, `THINKING` indicator auto-hides on next TEXT/BOARD_DRAW event.

### 5.5 Voice Mode Toggle Mid-Turn

**Scenario:** Student turns off voice while tutor is speaking.

**Client sends:** `{type: "VOICE_MODE", enabled: false}`

**Server:** Sets `router.voice_enabled = false`. Remaining beats get `AUDIO_SKIP` instead of TTS calls. In-flight TTS tasks are NOT cancelled (they'll complete but the audio frame will be dropped by client since voice is off).

**Client:** On voice mode off → stop current audio, set all pending beats to skip, render remaining beats immediately.

### 5.6 Interrupt During Tool Call

**Scenario:** LLM called a tool, server is waiting for tool result. Student interrupts.

**Fix:** TurnQueue.cleanup() cancels the task that's awaiting the tool result. The tool may still execute (DB queries can't be cancelled), but its result is discarded because the TurnQueue is dead.

### 5.7 Rapid-Fire Interrupts

**Scenario:** Student sends 3 messages quickly. Each triggers interrupt of the previous.

**Fix:** SessionRouter.handle_message() always cleans up the active turn first:
```python
async def handle_message(self, ...):
    if self.active_turn:
        await self.active_turn.cleanup()  # kill previous
    # ... start new turn
```

Generation counter ensures only the latest turn's events reach the client.

### 5.8 Binary Frame During Reconnect

**Scenario:** Client reconnects. Receives a stale binary frame from the old connection.

**Fix:** New WebSocket connection → new `activeGeneration` on client. All frames from previous connection have old generation → dropped.

### 5.9 ElevenLabs Rate Limiting

**Scenario:** Multiple concurrent users exhaust the API key's rate limit.

**Detection:** ElevenLabs returns 429.

**Fix:** All beats in the turn fall back to AUDIO_SKIP. Log the rate limit event. Session continues silently. Consider: per-session TTS budget (e.g., 50 beats/session max).

### 5.10 Audio Playback Blocked (Autoplay Policy)

**Scenario:** Browser blocks audio autoplay because user hasn't interacted with the page.

**Fix:** First beat's `audio.play()` rejects. Client catches the error:
```javascript
audio.play().catch(() => {
    // Show "Click to enable audio" banner
    showAudioUnlockBanner();
    // Continue rendering beats without audio
    currentBeat++;
    tryPlayNext();
});
```

After user clicks, subsequent `audio.play()` calls succeed.

---

## 6. Migration Strategy

### Phase 1: Add WebSocket endpoint alongside SSE (non-breaking)

1. Build `turn_queue.py`, `session_router.py`, `ws_chat.py`
2. Mount `/ws/chat` in `main.py` alongside existing `/api/chat`
3. Reuse existing `generate()` internals — extract into shared functions
4. Test WebSocket path independently

### Phase 2: Client WebSocket mode (feature flag)

1. Add `connectWS()` and beat queue player to `app.js`
2. Feature flag: `state.useWebSocket = true` → use WS, else SSE
3. Keep `streamADK()` intact as fallback
4. Test both paths in parallel

### Phase 3: Remove SSE + client TTS

1. Remove `streamADK()` fetch-based SSE code
2. Remove `voiceFetchTTS()`, `voiceSpeak()`, eager beat watcher TTS calls
3. Remove `/api/tts` proxy endpoint
4. Remove `_eager` TTS prefetching logic
5. Keep `_eager` beat parsing for non-audio concerns (board draw, cursor, etc.) OR move parsing to server

### What stays on the client:
- Board draw execution (`BoardEngine`, `executeDraw()`)
- Beat attribute parsing (draw JSON, cursor, annotations) — unless moved to server
- Audio playback (simple: receive blob → play)
- Pause/resume/speed (audio element controls)
- UI rendering (subtitles, voice bar, question input)

### What moves to the server:
- TTS API calls
- Beat text → audio conversion
- Audio failure handling / skip logic
- Turn lifecycle management

---

## 7. File Changes Summary

### New files:
- `backend/app/services/turn_queue.py` — TurnQueue class
- `backend/app/services/session_router.py` — SessionRouter class
- `backend/app/api/routes/ws_chat.py` — WebSocket endpoint
- `backend/app/services/tts_service.py` — ElevenLabs TTS wrapper

### Modified files:
- `backend/app/main.py` — mount WebSocket route
- `backend/app/api/routes/chat.py` — extract shared logic from `generate()` into reusable functions
- `frontend/app.js` — replace SSE + client TTS with WebSocket + beat queue player

### Eventually removed:
- `/api/tts` endpoint in `main.py`
- Client-side TTS code (~500 lines in `app.js`)
- `_eager.ttsPrefetch` logic

---

## 8. Testing Checklist

- [ ] Normal flow: message → beats stream → audio plays → board draws
- [ ] TTS failure: ElevenLabs down → beats render silently
- [ ] Interrupt: student types mid-speech → old turn killed, new turn starts
- [ ] Cancel: student clicks stop → silence, system idle
- [ ] Rapid interrupt: 3 messages in 2 seconds → only last turn survives
- [ ] Pause/resume: audio pauses/resumes, board holds position
- [ ] Speed: 1x → 1.5x → 2x mid-playback
- [ ] Voice toggle: off mid-turn → remaining beats render silently
- [ ] Connection drop: WiFi off → reconnect → session intact
- [ ] Tab background: return to tab → audio context resumes
- [ ] Tool call: long tool → "thinking" indicator → resumes
- [ ] Autoplay blocked: first visit → fallback to silent → unlock banner
- [ ] Assessment: MCQ renders on board during voice turn
- [ ] Video mode: video control events (RESUME/SEEK) work over WS
- [ ] Concurrent sessions: multiple tabs → independent turn queues
