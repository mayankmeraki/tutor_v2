# Voice Bar Loading States — Spec

## Overview

Document and improve all loading/state behaviors in the voice bar. The voice bar has four states (`idle`, `thinking`, `speaking`, `paused`) plus several loading indicators. Several are unused or could provide better feedback.

---

## Current Behaviors (As-Is)

### State Machine

```
IDLE → [user submits] → THINKING → [first beat plays] → SPEAKING → [all done] → IDLE
                                                            ↕
                                                         PAUSED
```

### State: IDLE

| Element | Behavior |
|---------|----------|
| Textarea | Enabled, placeholder "Your answer..." |
| Send button | Visible when textarea has content |
| Mic button | Visible, mic icon |
| Stop button | Hidden |
| Pause/Resume | Hidden |
| Progress bar | Hidden (element exists, always `display: none`) |
| Status text | Hidden (element exists, always `display: none`) |
| Aura glow | None |
| Subtitle bar | Hidden |
| Board indicator | Hidden |

### State: THINKING

Triggered by: `streamADK()` → `setVoiceBarState('thinking')`

| Element | Behavior |
|---------|----------|
| Textarea | Disabled, 40% opacity, placeholder "Generating..." |
| Send button | Hidden |
| Mic button | Hidden (unless Scribe active) |
| Stop button | Visible |
| Progress bar | CSS class `active thinking` but `display: none` — **UNUSED** |
| Status text | CSS class `active thinking` but `display: none` — **UNUSED** |
| Aura glow | None |
| Subtitle bar | Shows "You: ..." for 2s, then hides |
| Board indicator | `_showBoardStreaming()` — pulse on board canvas |
| Mic (via voiceBarSetThinking) | Swapped to red stop icon, pulsing `vb-think-pulse` 1.8s |

**Issues:**
- Progress bar exists but is never visible — wasted feedback opportunity
- No visual indicator ON the voice bar itself that processing is happening (textarea just goes dim)
- Two stop buttons appear (mic-as-stop + stop button) — redundant
- If AI takes >2s, subtitle "You: ..." hides and there's no feedback until speaking starts

### State: SPEAKING

Triggered by: first beat executes or first TTS chunk plays

| Element | Behavior |
|---------|----------|
| Textarea | Enabled, placeholder "Type to interrupt..." |
| Send button | Hidden |
| Stop button | Visible |
| Pause button | Visible |
| Aura glow | Warm orange blobs behind voice bar (`euler-speaking` class), `aura-blob1` 2s animation |
| Subtitle bar | Shows current speech text, updates as tutor speaks |
| Mic button | Green pulsing `vb-speak-pulse` 2s |
| Board indicator | Hidden (first beat took over) |

**Issues:**
- Transition from thinking→speaking is abrupt (no ease-in for aura)
- Aura is static animation, doesn't react to actual audio

### State: PAUSED

Triggered by: user clicks pause during speaking

| Element | Behavior |
|---------|----------|
| Textarea | Enabled, focused, placeholder "Paused — type or resume" |
| Resume button | Visible, green pulsing `vbResumePulse` 1.5s |
| Status text | CSS class `active paused`, text "Paused" — **BUT `display: none`** |
| Audio | Paused (AudioContext suspended, HTML audio paused) |
| Board | Execution paused |

**Issues:**
- Status text "Paused" is set but element is `display: none` — user never sees it

### Other Loading Indicators

#### Session Prep Overlay
- Full-screen overlay with pulsing orb
- Shows messages: "Preparing your session...", "Loading course materials...", etc.
- Fades out after 500ms when complete
- **Working correctly** — no issues

#### Board Streaming Indicator
- Dynamic element appended to board canvas
- Shows pulse while waiting for first beat
- Hidden when first beat executes
- **Working correctly** — no issues

#### Inline Mic Waveform Overlay
- Shows waveform bars + "Listening..." on textarea
- Appears on mic tap, disappears on VAD commit or stop
- **Working correctly** — just added

---

## Proposed Improvements

### Improvement 1: Activate the Progress Bar

**Current:** `vb-progress` element has CSS classes set but is always `display: none`.

**Proposed:** Show a thin animated bar at the top of the voice bar during thinking state.

- Thin line (2px height) at the top edge of `.voice-bar`, inside the border radius
- Indeterminate animation: a shimmer/gradient that slides left-to-right continuously
- Color: accent green `#34d399` at 60% opacity
- Appears on thinking state, disappears on speaking/idle
- Smooth fade-in/fade-out (200ms)

### Improvement 2: Thinking Shimmer on Voice Bar

**Current:** Textarea goes to 40% opacity with "Generating..." placeholder. No animation on the bar itself.

**Proposed:** Add a subtle shimmer/pulse on the voice bar border during thinking.

- Border color pulses between `rgba(52,211,153,0.1)` and `rgba(52,211,153,0.3)` 
- Duration: 2s ease-in-out infinite
- Gives the bar a "breathing" feel while waiting
- Complements the progress bar above

### Improvement 3: Single Stop Button During Thinking/Speaking

**Current:** During thinking, both the mic button (swapped to stop icon via `voiceBarSetThinking`) AND the `voice-bar-stop` button appear. Two stop buttons side by side — confusing and redundant.

**Proposed:** Only one stop button during thinking and speaking states:
- Keep the dedicated `voice-bar-stop` button — it's already in the bottom-left controls area
- Hide the mic button entirely during thinking and speaking states (it has no mic function during those states anyway)
- Remove the `voiceBarSetThinking` logic that swaps the mic icon to a stop icon and changes its onclick to `stopGeneration` — this whole mechanism becomes unnecessary
- Mic button reappears when state returns to idle

### Improvement 4: Show Status Text During Paused

**Current:** Status text "Paused" is set but the element is `display: none`.

**Proposed:** Make `.vb-status` visible when it has the `active paused` class:
- Small text "Paused" appears between progress bar and textarea
- Muted color, 12px font size
- Only visible during paused state

### Improvement 5: Persistent "You said" Until Tutor Speaks

**Current:** "You: ..." subtitle shows for 2s during thinking, then hides — leaving no feedback while waiting for the tutor.

**Proposed:** Keep the "You: ..." subtitle visible throughout the entire thinking state. Only hide/replace when the tutor starts speaking (the tutor's speech subtitle naturally replaces it). No timeout, no dimming — just stay there until the tutor takes over. Implementation: remove the 2s `setTimeout` in the thinking case of `setVoiceBarState` and instead let `voiceShowSubtitle` (called when the first beat plays) overwrite it naturally.

### Improvement 6: Mic Button Connection Feedback

**Current:** When user taps mic, there's no visual feedback while Scribe WS is connecting (~1-2s). Waveform appears only after connection succeeds.

**Proposed:** Show a brief "connecting" state on the mic button:
- Mic button gets a pulsing border animation immediately on tap
- "Listening..." text in overlay changes to "Connecting..." until `ready` message
- If connection fails, toast shows error

### Improvement 7: Smooth Speaking Aura Transition

**Current:** The warm orange aura appears instantly when speaking starts.

**Proposed:** Fade the aura in over 400ms for a smoother transition from thinking to speaking. Add `transition: opacity 0.4s ease` to the aura pseudo-elements.

---

## Priority Order

1. **Improvement 1** (Progress bar) — highest impact, element already exists
2. **Improvement 2** (Thinking shimmer) — complements progress bar
3. **Improvement 5** (Persistent "You said") — simple change, better feedback
4. **Improvement 3** (Remove duplicate stop) — cleanup, reduces confusion
5. **Improvement 7** (Smooth aura) — polish
6. **Improvement 4** (Paused status) — minor but fixes broken feature
7. **Improvement 6** (Mic connection) — nice-to-have

## Out of Scope

- Aura reacting to audio amplitude (complex, separate feature)
- Redesigning the session prep overlay (working fine)
- Board streaming indicator changes (working fine)
