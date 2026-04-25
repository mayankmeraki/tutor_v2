# Inline Mic Input — Spec

## Overview

Replace the current two-mode (Type / Speak) voice bar with a single unified input box. The textarea is always visible. A mic button in the bottom-right corner lets users tap to start voice input. Voice-captured text is auto-sent via ElevenLabs Scribe VAD. No mode switching, no separate speak UI — just a mic button that temporarily activates listening inline.

## User Journey

### Default State (Typing)

```
┌─────────────────────────────────────┐
│  Type your response...              │
├─────────────────────────────────────┤
│  📎                          → 🎤  │
└─────────────────────────────────────┘
```

- Textarea is editable, placeholder "Type your response..."
- Bottom row: attach (left), send + mic (right)
- Send button appears when textarea has content
- Mic button is always visible in the bottom-right

### Listening State (After Mic Tap)

```
┌─────────────────────────────────────┐
│  ▎▌▎▌▎▌▎  Listening...             │  ← waveform + text overlay
├─────────────────────────────────────┤
│  📎                          → ■   │  ← mic becomes stop icon
└─────────────────────────────────────┘
```

- Tap mic button → mic activates, Scribe WS opens
- Textarea area shows a waveform animation + "Listening..." text (overlaid, textarea content preserved underneath)
- Mic button icon changes to a stop/square icon
- Waveform bars react to mic audio levels (via AnalyserNode)
- Any existing typed text in the textarea is preserved (hidden behind the overlay but not cleared)

### VAD Commits → Auto-Send

1. ElevenLabs Scribe VAD detects end-of-utterance, sends `committed_transcript`
2. If textarea had existing typed text: append spoken text after it (with a space separator)
3. If textarea was empty: spoken text becomes the full message
4. Send immediately (call `submitVoiceBarInput()` or equivalent)
5. Textarea clears, mic turns off, back to default typing state
6. Waveform overlay disappears

### Stop/Dismiss (Tap Stop While Listening)

1. User taps the stop button (was mic button) while listening
2. Scribe WS closes, mic stops capturing
3. Any partial transcript is discarded — nothing is sent
4. If there was pre-existing typed text, it remains in the textarea untouched
5. Waveform overlay disappears, mic button icon restores to mic
6. Back to default typing state

## UI Components

### Mic Button (`.vb-mic-toggle`)

- Position: bottom-right of voice bar, next to send button
- Default icon: microphone SVG
- Listening state: changes to stop/square icon, subtle green tint or border to indicate active
- Click handler: toggles listening on/off

### Waveform Overlay

- Overlays the textarea area (not the bottom controls row)
- Semi-transparent dark background so it's visually distinct
- Left side: 5-7 waveform bars (2.5px wide, animate with mic audio levels)
- Right side: "Listening..." label in muted white
- Uses `position: absolute` over the textarea, does not alter textarea DOM content
- Appears on mic tap, disappears on send or stop

### No Changes to Bottom Controls

- Attach button, send button, pause/resume/stop tutor buttons — all remain as-is
- Only the mic button icon swaps between mic and stop states

## Technical Implementation

### Audio Pipeline (reuse existing)

- `getUserMedia({ audio: true })` → mic stream
- `AudioContext` at 16kHz sample rate
- `AnalyserNode` (fftSize=256) for waveform visualization
- `ScriptProcessorNode` (buffer 4096) for PCM16 encoding
- Float32 → Int16 conversion → base64 → JSON to Scribe WS

### Scribe WebSocket (reuse existing backend)

- Connect to `/ws/scribe` on mic tap
- Send `{ type: "audio", data: "<base64>" }` chunks
- Receive `{ type: "committed", text: "..." }` → auto-send
- Receive `{ type: "partial", text: "..." }` → ignored (not shown in this design)
- Disconnect on stop or after auto-send

### State Management

No separate `inputMode` state needed. Just a boolean `_listening` flag:

- `_listening = false` → default typing state
- `_listening = true` → mic active, waveform showing, scribe connected

### Lifecycle

```
Mic tap
  → getUserMedia (if not already acquired)
  → open Scribe WS
  → start audio capture + waveform animation
  → show waveform overlay on textarea
  → swap mic icon to stop icon

VAD commit received
  → get committed text
  → append to any existing textarea content
  → call submit
  → close Scribe WS
  → stop audio capture
  → hide waveform overlay
  → restore mic icon
  → release mic stream

Stop tap
  → close Scribe WS
  → stop audio capture
  → discard any partial text
  → hide waveform overlay
  → restore mic icon
  → release mic stream
  → textarea content untouched
```

## Edge Cases

1. **Typed text + mic**: Existing textarea text is preserved. On VAD commit, spoken text is appended with a space separator, then the combined text is sent.

2. **Stop while listening**: Discard everything spoken. Typed text remains in textarea. Back to idle.

3. **Mic tap while tutor is responding**: Stop tutor response first (`stopAll()`), then start listening.

4. **Mic permission denied**: Show a toast "Microphone access required" and stay in typing state.

5. **Scribe WS connection failure**: Show a toast "Voice input unavailable", stop listening, restore mic icon.

6. **Rapid double-tap mic**: Debounce (300ms). Ignore second tap.

7. **Send button tap while listening**: Stop listening, discard spoken text, send whatever is in the textarea (typed text only).

8. **User types while listening**: The textarea is overlaid by the waveform, so typing is blocked during listening. The overlay captures focus.

## What to Remove

- The entire `SpeakMode` IIFE module (enter/exit/toggle, separate speak UI)
- `#vb-speak-content` div and all its children (orb, speak-transcript, speak-bottom, etc.)
- All `.vb-speak-content` CSS and orb/waveform CSS tied to the old speak mode
- `state.inputMode` — no longer needed
- `.speak-keyboard-btn`, `.speak-mic-active`, `.speak-orb-*` styles
- `SpeakMode.toggle()` onclick handler on mic button → replace with inline mic logic
- Old speak mode drag handler exclusions (`.speak-orb-container`, etc.)

## What to Keep / Reuse

- Backend `scribe.py` WebSocket relay — no changes needed
- Audio pipeline logic (getUserMedia, AudioContext, PCM16 encoding) — extract from old SpeakMode
- Scribe WS connection logic — extract from old SpeakMode
- Mic button element (`.vb-mic-toggle`) — just change its onclick and icon swap behavior
- Waveform bar rendering logic — reuse but move into textarea overlay
