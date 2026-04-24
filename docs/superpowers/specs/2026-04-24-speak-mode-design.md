# Speak Mode: Always-On Voice Input for Euler Tutor

**Date:** 2026-04-24
**Status:** Approved
**Approach:** ElevenLabs Scribe Realtime STT with native VAD

---

## Problem

Students currently interact with the tutor by typing in a textarea. This creates friction in the conversational flow, especially for younger learners or during rapid back-and-forth exchanges. The tutor already speaks via TTS, but the student must type responses.

## Solution

Add a persistent **speak mode** alongside the existing type mode. In speak mode:
- The textarea transforms into an animated orb/waveform visualization
- The microphone is always hot (ElevenLabs Scribe WebSocket stays connected)
- Speech is auto-submitted when ElevenLabs VAD detects end-of-utterance (`committed_transcript`)
- Speaking while the tutor is responding triggers an immediate interrupt
- No clicks needed between turns -- fully hands-free conversational loop
- Live transcription of what the student is saying appears below the orb

## Architecture

### Input Mode State

A new top-level state variable `state.inputMode` with two values:
- `'type'` (default) -- current behavior
- `'speak'` -- always-on voice input

This is orthogonal to the existing voice bar states (`idle`, `thinking`, `speaking`, `paused`), which continue to govern tutor-side behavior.

### Mode Toggle

- **Type -> Speak:** Student clicks mic icon button (right side of voice bar bottom row). Requests `getUserMedia`, opens Scribe WebSocket, transforms UI.
- **Speak -> Type:** Student clicks keyboard/type button (bottom-left of speak mode UI). Closes Scribe WebSocket, releases mic stream, transforms UI back to textarea.

Mode persists across tutor turns. Switching modes does not interrupt the tutor if streaming.

### Scribe WebSocket Lifecycle

In speak mode, the `/ws/scribe` WebSocket connection stays open continuously:

1. **On enter speak mode:** `getUserMedia({audio: true})` to get mic stream. Open WebSocket to `/ws/scribe`. Wait for `ready` message. Begin sending PCM16 audio chunks (16kHz, base64-encoded).
2. **During conversation:** Connection stays open across multiple student/tutor turns. No reconnect needed between turns.
3. **On exit speak mode:** Send `{type: "stop"}` to close Scribe WebSocket. Stop `MediaRecorder`/`ScriptProcessor`. Release mic stream (`track.stop()`).
4. **On disconnect/error:** Show brief error toast, attempt reconnect. If reconnect fails 3 times, fall back to type mode with a notification.

### Audio Capture

Use `AudioContext` + `ScriptProcessorNode` (or `AudioWorkletNode` where supported) to:
1. Capture raw PCM16 from `getUserMedia` stream at 16kHz
2. Send base64-encoded chunks to `/ws/scribe` every ~250ms
3. Simultaneously feed an `AnalyserNode` for real-time waveform visualization

### VAD and Auto-Submit

ElevenLabs Scribe handles Voice Activity Detection natively:
- `partial` messages update the live transcription UI
- `committed` message (VAD detected end-of-utterance) triggers auto-submit:
  1. Capture the committed text
  2. Show "You: {text}" in the subtitle bar briefly
  3. Call `streamADK(text)` (same path as type mode)
  4. Clear transcription display
  5. Mic stays hot -- no restart needed

No hardcoded silence timeout. The 1.5s timer in the existing `scribeStart()` is not used.

### Interrupt Behavior

The mic is always listening, even during tutor streaming. Interrupt logic:

1. While tutor is streaming (`state.isStreaming === true`):
   - Any `partial` transcript with length > 5 chars triggers `stopAll()` immediately
   - The student's speech continues being captured
   - On `committed`, the text is auto-submitted as normal
2. This replaces the current interrupt model where the student must click stop or type

### Existing Code Changes

The current `scribeStart()`/`scribeStop()`/`scribeMute()` functions (app.js:1217-1331) use the browser's Web Speech API. In speak mode, these are NOT used. Instead, a new `SpeakMode` module handles the ElevenLabs Scribe connection. The existing Scribe code remains for any legacy/fallback usage.

---

## UI Design

### Type Mode (Default -- unchanged)

The current voice bar with textarea, attach button, send button. A new mic toggle button is added to the bottom-right, next to the send button.

```
+-------------------------------------------+
| Your answer...                            |
| [attach]                    [Send] [Mic]  |
+-------------------------------------------+
```

### Speak Mode: Idle (waiting for speech)

Textarea is hidden. An animated orb replaces it. Warm amber color, gentle pulse animation.

```
+-------------------------------------------+
|              ( gentle orb )               |
|             "Listening..."                |
| [Type]                            [Mic*]  |
+-------------------------------------------+
```

### Speak Mode: Listening (speech detected)

Orb turns green. Waveform bars animate reactively based on actual mic audio levels (via `AnalyserNode.getByteFrequencyData()`). Live transcription appears below orb.

```
+-------------------------------------------+
|            ( green waveform )             |
|   "I think you'd use classes for each..." |
| [Type]                            [Mic*]  |
+-------------------------------------------+
```

### Speak Mode: Tutor Responding (mic still hot)

Orb turns purple with a glow aura (matching the existing `euler-speaking` aura). Stop and pause buttons appear. Prompt text changes to "Speak to interrupt...". Mic stays hot.

```
+-------------------------------------------+
|    [purple aura]                          |
|            ( purple waveform )            |
|         "Speak to interrupt..."           |
| [Stop] [Pause]                    [Mic*]  |
+-------------------------------------------+
```

### Waveform Animation Strategy

| State | Animation | Source |
|-------|-----------|--------|
| Idle | Gentle ambient pulse | CSS keyframes (generic) |
| Listening | Reactive waveform bars | `AnalyserNode` from mic `getUserMedia` stream |
| Tutor Responding | Slow ambient purple pulse | CSS keyframes (generic) |

### Color Palette

| State | Primary Color | Meaning |
|-------|--------------|---------|
| Idle | `rgba(201, 184, 150)` warm amber | Ready, waiting |
| Listening | `#34d399` green | Active input |
| Tutor Responding | `#8b5cf6` purple | Tutor speaking |

These colors align with the existing codebase: green is already used for `scribe-active`, purple/violet for the `euler-speaking` aura.

---

## Data Flow

### Student speaks in speak mode:

```
Mic (getUserMedia)
  |
  +---> AudioContext -> AnalyserNode -> requestAnimationFrame -> waveform bars
  |
  +---> ScriptProcessor -> PCM16 base64 chunks
          |
          v
      WebSocket /ws/scribe
          |
          v
      Backend relay -> ElevenLabs Scribe API
          |
          v
      partial/committed transcripts back via WS
          |
          v
      Frontend SpeakMode handler:
        - partial -> update transcription UI
        - committed -> streamADK(text) -> same pipeline as type mode
```

### Interrupt flow:

```
Tutor streaming (state.isStreaming = true)
  +-- Student speaks
  |     partial transcript arrives (len > 5)
  |       -> stopAll() immediately
  |     Student keeps speaking
  |     committed transcript arrives
  |       -> streamADK(text)
  |       -> tutor starts new response
  |       -> mic stays hot throughout
```

---

## Module Structure

### New: `SpeakMode` module (frontend/app.js)

Responsible for:
- `SpeakMode.enter()` -- request mic, open Scribe WS, transform UI
- `SpeakMode.exit()` -- close Scribe WS, release mic, restore textarea UI
- `SpeakMode.isActive()` -- returns boolean
- `SpeakMode._onPartial(text)` -- update transcription, check for interrupt
- `SpeakMode._onCommitted(text)` -- auto-submit via `streamADK()`
- `SpeakMode._startAudioCapture()` -- getUserMedia + AudioContext + AnalyserNode + ScriptProcessor
- `SpeakMode._stopAudioCapture()` -- release all audio resources
- `SpeakMode._animateWaveform()` -- rAF loop reading AnalyserNode data
- `SpeakMode._connectScribe()` -- open /ws/scribe WebSocket
- `SpeakMode._disconnectScribe()` -- close WebSocket cleanly

### Changes to existing code

1. **`setVoiceBarState()`** -- add speak mode awareness. When `state.inputMode === 'speak'`:
   - `idle` -> show speak-idle UI (orb, "Listening...")
   - `thinking` -> show speak-idle UI with "Thinking..." text
   - `speaking` -> show speak-tutor UI (purple orb, interrupt prompt)
   - `paused` -> show speak-tutor UI with pause state

2. **`submitVoiceBarInput()`** -- no changes needed. `streamADK()` is called directly by SpeakMode.

3. **`stopAll()`** -- no changes needed. SpeakMode mic stays hot through stopAll since the Scribe WS is independent of the tutor streaming pipeline.

4. **`index.html`** -- add mic toggle button to type mode bottom row. Add speak mode container (orb, transcript, controls) as a sibling to the textarea, toggled by CSS class.

5. **`styles.css`** -- add speak mode styles: orb, waveform, transitions, color states.

### Backend changes

None required. The existing `/ws/scribe` endpoint handles everything needed. The ElevenLabs Scribe API provides native VAD via `committed_transcript` messages.

---

## Edge Cases

1. **Mic permission denied:** Show toast "Microphone access required for speak mode", stay in type mode.
2. **Scribe WS disconnects mid-conversation:** Attempt reconnect (3 retries with backoff). On failure, auto-switch to type mode with toast "Voice connection lost, switched to typing."
3. **Student switches mode while tutor is streaming:** Mode switches without interrupting the tutor. If switching to speak mode, mic starts listening immediately (can interrupt). If switching to type mode, Scribe WS closes, textarea appears.
4. **Browser tab loses focus:** Keep Scribe WS open but mute the mic capture to avoid background noise triggering interrupts. Resume on tab focus.
5. **Multiple rapid interrupts:** Throttled by the existing 800ms guard in `streamADK()`.
6. **Empty committed transcript:** Ignore (don't submit empty strings).
7. **Very long utterances:** ElevenLabs Scribe may emit multiple `committed` chunks. Accumulate all committed text, use a short debounce (~500ms after last committed with no new partial) before submitting.

---

## Browser Compatibility

- **Required APIs:** `getUserMedia`, `AudioContext`, `WebSocket`
- **Supported:** Chrome 74+, Firefox 76+, Safari 14.1+, Edge 79+
- **Fallback:** If `getUserMedia` is not available, hide the mic toggle button entirely. Type mode only.

---

## Testing Plan

1. Enter speak mode, verify orb appears with gentle pulse
2. Speak a sentence, verify green waveform reacts to audio levels
3. Stop speaking, verify ElevenLabs VAD triggers auto-submit (no fixed timeout)
4. Verify tutor responds, orb turns purple, "Speak to interrupt..." appears
5. Speak while tutor is responding, verify immediate interrupt + new response
6. Verify hands-free loop: speak -> tutor responds -> speak again, no clicks
7. Click keyboard button, verify return to type mode with textarea
8. Deny mic permission, verify graceful fallback
9. Kill network mid-conversation, verify reconnect + fallback behavior
10. Test on Chrome, Firefox, Safari
