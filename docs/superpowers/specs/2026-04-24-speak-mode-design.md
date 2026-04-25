# Speak Mode: Tap-to-Talk Voice Input for Euler Tutor

**Date:** 2026-04-24
**Status:** Draft
**Approach:** Tap-to-start mic, ElevenLabs Scribe Realtime STT with native VAD to auto-end

---

## Problem

Students currently interact with the tutor by typing in a textarea. This creates friction in the conversational flow, especially for younger learners or during rapid back-and-forth exchanges. The tutor already speaks via TTS, but the student must type responses.

An always-on mic approach picks up ambient noise, other voices, and background conversations — creating a poor experience, especially in classrooms, cafes, or shared spaces.

## Solution

Add a **speak mode** alongside the existing type mode using a **tap-to-start, VAD-to-end** pattern:

- Student **taps the mic button** to start speaking (no ambient noise pickup when idle)
- ElevenLabs Scribe VAD **automatically detects end-of-utterance** and submits (no need to tap stop)
- Live transcription of what the student is saying appears below the orb
- Speaking while the tutor is responding triggers an immediate interrupt
- Orb/waveform visualization provides clear visual feedback of mic state
- Between turns, mic is **off** — no accidental triggers from ambient noise

This is the same pattern used by ChatGPT voice mode, Google Translate, and most modern AI chat apps.

## Architecture

### Input Mode State

A new top-level state variable `state.inputMode` with two values:
- `'type'` (default) -- current behavior
- `'speak'` -- tap-to-talk voice input

This is orthogonal to the existing voice bar states (`idle`, `thinking`, `speaking`, `paused`), which continue to govern tutor-side behavior.

### Mode Toggle

- **Type -> Speak:** Student clicks mic icon button (right side of voice bar bottom row). Requests `getUserMedia`, transforms UI to show orb. Mic is **not yet active** — orb shows idle state.
- **Speak -> Type:** Student clicks keyboard/type button (bottom-left of speak mode UI). Releases mic stream, transforms UI back to textarea.

Mode persists across tutor turns. Switching modes does not interrupt the tutor if streaming.

### Mic Lifecycle (Tap-to-Start, VAD-to-End)

The key difference from always-on: the mic and Scribe WebSocket are only active while the student is speaking.

1. **Idle in speak mode:** Orb shows amber idle state. Mic is off. No Scribe WebSocket connection. Student sees "Tap to speak" prompt.
2. **Student taps mic/orb:** `getUserMedia` stream starts (or resumes if already granted). Scribe WebSocket opens to `/ws/scribe`. Audio capture begins. Orb turns green with reactive waveform. Transcript shows "Listening...".
3. **Student speaks:** Partial transcripts update the UI in real-time. Waveform reacts to audio levels.
4. **Student stops speaking:** ElevenLabs VAD detects silence and sends `committed_transcript`. Auto-submit fires:
   - Show "You: {text}" in subtitle bar
   - Call `streamADK(text)`
   - Close Scribe WebSocket
   - Stop audio capture
   - Orb returns to idle (amber)
5. **Tutor responds:** Orb turns purple. Student can tap mic/orb again to interrupt (which triggers `stopAll()` and starts a new listen cycle).
6. **Tutor finishes:** Orb returns to idle (amber). "Tap to speak" prompt returns.

### Audio Capture

Use `AudioContext` + `ScriptProcessorNode` (or `AudioWorkletNode` where supported) to:
1. Capture raw PCM16 from `getUserMedia` stream at 16kHz
2. Send base64-encoded chunks to `/ws/scribe` every ~250ms
3. Simultaneously feed an `AnalyserNode` for real-time waveform visualization

Audio resources are created on first tap and reused across taps within the same speak mode session. The `getUserMedia` stream stays open while in speak mode to avoid repeated permission prompts, but audio is only processed and sent when actively listening.

### VAD and Auto-Submit

ElevenLabs Scribe handles Voice Activity Detection natively:
- `partial` messages update the live transcription UI
- `committed` message (VAD detected end-of-utterance) triggers auto-submit:
  1. Capture the committed text
  2. Show "You: {text}" in the subtitle bar briefly
  3. Call `streamADK(text)` (same path as type mode)
  4. Close Scribe WS and stop sending audio
  5. Return to idle state

No hardcoded silence timeout. The `committed_transcript` from ElevenLabs is the sole signal for end-of-utterance.

### Interrupt Behavior

Interrupting the tutor uses the same tap-to-start pattern:

1. While tutor is streaming (`state.isStreaming === true`):
   - Student taps the mic/orb
   - `stopAll()` fires immediately, stopping the tutor
   - Scribe WebSocket opens, mic starts capturing
   - Student speaks their interruption
   - On `committed_transcript`, auto-submit as normal
2. This replaces the current interrupt model where the student must click stop or type

### Existing Code Changes

The current `scribeStart()`/`scribeStop()`/`scribeMute()` functions (app.js) use the browser's Web Speech API. In speak mode, these are NOT used. Instead, a new `SpeakMode` module handles the ElevenLabs Scribe connection. The existing Scribe code remains for any legacy/fallback usage.

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

### Speak Mode: Idle (mic off, waiting for tap)

Textarea is hidden. An animated orb replaces it. Warm amber color, gentle pulse animation. Clear prompt to tap.

```
+-------------------------------------------+
|              ( gentle orb )               |
|            "Tap to speak"                 |
| [Type]                            [Mic]   |
+-------------------------------------------+
```

The orb and the mic button are both tappable to start listening.

### Speak Mode: Listening (mic on, speech being captured)

Orb turns green. Waveform bars animate reactively based on actual mic audio levels (via `AnalyserNode.getByteFrequencyData()`). Live transcription appears below orb. Mic button shows active state (pulsing green ring).

```
+-------------------------------------------+
|            ( green waveform )             |
|   "I think you'd use classes for each..." |
| [Type]                         [Mic(on)]  |
+-------------------------------------------+
```

### Speak Mode: Tutor Responding (mic off, can tap to interrupt)

Orb turns purple with a glow aura (matching the existing `euler-speaking` aura). Stop and pause buttons appear. Prompt tells student they can tap to interrupt.

```
+-------------------------------------------+
|    [purple aura]                          |
|            ( purple waveform )            |
|         "Tap mic to interrupt"            |
| [Stop] [Pause]                    [Mic]   |
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
| Idle | `rgba(201, 184, 150)` warm amber | Ready, waiting for tap |
| Listening | `#34d399` green | Mic active, capturing speech |
| Tutor Responding | `#8b5cf6` purple | Tutor speaking |

These colors align with the existing codebase: green is already used for `scribe-active`, purple/violet for the `euler-speaking` aura.

---

## Data Flow

### Student taps mic and speaks:

```
Student taps mic/orb
  |
  v
getUserMedia (or resume existing stream)
  |
  +---> AudioContext -> AnalyserNode -> requestAnimationFrame -> waveform bars
  |
  +---> ScriptProcessor -> PCM16 base64 chunks
          |
          v
      WebSocket /ws/scribe (opened on tap)
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
        - committed -> streamADK(text) -> close Scribe WS -> return to idle
```

### Interrupt flow:

```
Tutor streaming (state.isStreaming = true)
  +-- Student taps mic/orb
  |     -> stopAll() immediately
  |     -> open Scribe WS, start audio capture
  |     Student speaks
  |     partial transcript arrives -> update UI
  |     committed transcript arrives
  |       -> streamADK(text)
  |       -> close Scribe WS
  |       -> tutor starts new response
  |       -> return to idle (mic off)
```

---

## Module Structure

### New: `SpeakMode` module (frontend/app.js)

Responsible for:
- `SpeakMode.enter()` -- request mic permission, transform UI to speak mode (mic stays off)
- `SpeakMode.exit()` -- release mic stream, restore textarea UI
- `SpeakMode.isActive()` -- returns boolean
- `SpeakMode.startListening()` -- open Scribe WS, start audio capture, update UI to listening state
- `SpeakMode.stopListening()` -- close Scribe WS, stop audio capture, return to idle
- `SpeakMode._onPartial(text)` -- update transcription UI
- `SpeakMode._onCommitted(text)` -- auto-submit via `streamADK()`, then `stopListening()`
- `SpeakMode._startAudioCapture()` -- getUserMedia + AudioContext + AnalyserNode + ScriptProcessor
- `SpeakMode._stopAudioCapture()` -- stop sending audio (keep stream open for reuse)
- `SpeakMode._animateWaveform()` -- rAF loop reading AnalyserNode data
- `SpeakMode._connectScribe()` -- open /ws/scribe WebSocket
- `SpeakMode._disconnectScribe()` -- close WebSocket cleanly

### Key state within SpeakMode

- `_active` -- whether speak mode is entered (UI shows orb)
- `_listening` -- whether mic is currently capturing and Scribe WS is open
- These are independent: `_active && !_listening` = idle orb, `_active && _listening` = green waveform

### Changes to existing code

1. **`setVoiceBarState()`** -- add speak mode awareness. When `state.inputMode === 'speak'`:
   - `idle` -> show speak-idle UI (orb, "Tap to speak")
   - `thinking` -> show speak-idle UI with "Thinking..." text
   - `speaking` -> show speak-tutor UI (purple orb, "Tap mic to interrupt")
   - `paused` -> show speak-tutor UI with pause state

2. **`submitVoiceBarInput()`** -- no changes needed. `streamADK()` is called directly by SpeakMode.

3. **`stopAll()`** -- no changes needed. SpeakMode handles its own cleanup.

4. **`index.html`** -- add mic toggle button to type mode bottom row. Add speak mode container (orb, transcript, controls) as a sibling to the textarea, toggled by CSS class. Orb and mic button both have `onclick` to `SpeakMode.startListening()`.

5. **`styles.css`** -- add speak mode styles: orb, waveform, transitions, color states, mic-active indicator.

### Backend changes

None required. The existing `/ws/scribe` endpoint handles everything needed. The ElevenLabs Scribe API provides native VAD via `committed_transcript` messages.

---

## Edge Cases

1. **Mic permission denied:** Show toast "Microphone access required for speak mode", stay in type mode.
2. **Scribe WS disconnects during active listening:** Show brief error toast, return orb to idle. Student can tap to try again.
3. **Student switches mode while tutor is streaming:** Mode switches without interrupting the tutor. If switching to speak mode, orb shows purple "Tap mic to interrupt". If switching to type mode, textarea appears.
4. **Browser tab loses focus while listening:** Stop listening (close Scribe WS, return to idle). This prevents runaway audio processing in background tabs.
5. **Multiple rapid taps:** Debounce mic tap to 300ms. If already listening, tap stops listening (cancel, don't submit).
6. **Empty committed transcript:** Ignore (don't submit empty strings).
7. **Very long utterances:** ElevenLabs Scribe may emit multiple `committed` chunks. Accumulate all committed text, use a short debounce (~500ms after last committed with no new partial) before submitting.
8. **Student taps mic during "thinking" state:** Allow it — opens mic for next turn. The previous query is still processing, new speech will queue or interrupt.

---

## Browser Compatibility

- **Required APIs:** `getUserMedia`, `AudioContext`, `WebSocket`
- **Supported:** Chrome 74+, Firefox 76+, Safari 14.1+, Edge 79+
- **Fallback:** If `getUserMedia` is not available, hide the mic toggle button entirely. Type mode only.

---

## Testing Plan

1. Enter speak mode, verify orb appears with idle amber pulse and "Tap to speak"
2. Tap mic, verify orb turns green with reactive waveform
3. Speak a sentence, stop speaking, verify VAD auto-submits (no tap needed to end)
4. Verify mic turns off after submit, orb returns to amber idle
5. Verify tutor responds, orb turns purple, "Tap mic to interrupt" appears
6. Tap mic while tutor is speaking, verify interrupt + new listen cycle
7. Verify no ambient noise pickup when orb is idle (mic off)
8. Click keyboard button, verify return to type mode with textarea
9. Deny mic permission, verify graceful fallback
10. Kill network mid-listen, verify error toast + return to idle
11. Test on Chrome, Firefox, Safari
