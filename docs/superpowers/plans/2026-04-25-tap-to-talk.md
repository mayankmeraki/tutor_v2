# Tap-to-Talk Speak Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tap-to-start, VAD-to-end speak mode to the voice bar so students can speak instead of type, with no ambient noise pickup between turns.

**Architecture:** A new `SpeakMode` IIFE module in `app.js` manages two independent states: `_active` (speak mode UI showing) and `_listening` (mic is on, Scribe WS open). The mic toggle button switches between type/speak modes. Tapping the orb or mic button starts a listen cycle — opens a Scribe WS, captures audio, sends to ElevenLabs. VAD `committed_transcript` auto-submits and closes the mic. Between turns the mic is off.

**Tech Stack:** ElevenLabs Scribe v2 Realtime STT (WebSocket), Web Audio API (`AudioContext`, `AnalyserNode`, `ScriptProcessorNode`), existing `/ws/scribe` backend relay.

**Spec:** `docs/superpowers/specs/2026-04-24-speak-mode-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/app/api/routes/scribe.py` | Modify | Fix ElevenLabs API message format (JSON `input_audio_chunk` instead of binary), correct URL params (`audio_format`, `commit_strategy`) |
| `frontend/index.html:1212-1219` | Modify | Add mic toggle button to `vb-bottom-right`, add speak mode overlay container (orb, transcript, controls) after `#voice-bar-main` |
| `frontend/styles.css` (append) | Modify | Add all speak mode styles: mic toggle, overlay, orb, waveform, color states, transitions |
| `frontend/app.js:811` | Modify | Add `inputMode: 'type'` to state object |
| `frontend/app.js` (after line ~1331) | Modify | Add `SpeakMode` IIFE module (~350 lines) |
| `frontend/app.js:19356-19444` | Modify | Add speak mode branch to `setVoiceBarState()` |

---

### Task 1: Fix Backend Scribe Relay

The existing `/ws/scribe` relay sends audio as raw binary frames, but ElevenLabs Scribe API expects JSON messages with `message_type: "input_audio_chunk"`. The URL also uses wrong parameter names.

**Files:**
- Modify: `backend/app/api/routes/scribe.py:5-7,34,121-139`

- [ ] **Step 1: Fix URL parameters**

In `backend/app/api/routes/scribe.py`, replace line 34:

```python
# OLD:
url = f"{SCRIBE_URL}?model_id=scribe_v2_realtime&language_code=en&sample_rate=16000"

# NEW:
url = (
    f"{SCRIBE_URL}?model_id=scribe_v2_realtime"
    f"&language_code=en"
    f"&audio_format=pcm_16000"
    f"&commit_strategy=vad"
)
```

- [ ] **Step 2: Fix audio message format**

Replace the audio sending block (lines 121-135). Instead of decoding base64 to binary, forward as JSON:

```python
# OLD:
if msg_type == "audio":
    audio_b64 = raw.get("data", "")
    if audio_b64 and scribe_ws:
        try:
            audio_bytes = base64.b64decode(audio_b64)
            await scribe_ws.send(audio_bytes)  # Binary frame to ElevenLabs
            _audio_count += 1
            if _audio_count <= 3 or _audio_count % 50 == 0:
                log.info("[Scribe] Audio chunk #%d (%d bytes → EL)", _audio_count, len(audio_bytes))

# NEW:
if msg_type == "audio":
    audio_b64 = raw.get("data", "")
    if audio_b64 and scribe_ws:
        try:
            el_msg = json.dumps({
                "message_type": "input_audio_chunk",
                "audio_base_64": audio_b64,
            })
            await scribe_ws.send(el_msg)
            _audio_count += 1
            if _audio_count <= 3 or _audio_count % 50 == 0:
                log.info("[Scribe] Audio chunk #%d → EL", _audio_count)
```

- [ ] **Step 3: Fix commit message format**

Replace the commit/flush block (lines 136-140):

```python
# OLD:
elif msg_type == "commit":
    # Trigger VAD flush
    if scribe_ws:
        try:
            await scribe_ws.send(json.dumps({"type": "flush"}))

# NEW:
elif msg_type == "commit":
    # Trigger manual commit
    if scribe_ws:
        try:
            await scribe_ws.send(json.dumps({"message_type": "input_audio_chunk", "audio_base_64": "", "commit": True}))
```

- [ ] **Step 4: Remove unused base64 import**

Remove `import base64` from line 7 (no longer decoding base64 to binary).

```python
# OLD:
import asyncio
import base64
import json

# NEW:
import asyncio
import json
```

- [ ] **Step 5: Verify server starts**

Run: `cd backend && python -c "from app.api.routes.scribe import ws_scribe; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes/scribe.py
git commit -m "fix(scribe): use correct ElevenLabs Scribe API message format and params"
```

---

### Task 2: Add Speak Mode HTML Elements

Add the mic toggle button to the voice bar and the speak mode overlay container (orb, transcript, controls).

**Files:**
- Modify: `frontend/index.html:1212-1219`

- [ ] **Step 1: Add mic toggle button and speak mode overlay**

In `frontend/index.html`, find the `vb-bottom-right` div (line 1212) and add a mic toggle button after the send button. Then add the speak mode overlay as a sibling after `#voice-bar-main` (after line 1218's closing `</div>`).

Replace lines 1212-1219 with:

```html
            <div class="vb-bottom-right">
              <button class="vb-send-btn visible" id="voice-bar-send" onclick="submitVoiceBarInput()" title="Send (Enter)">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
              </button>
              <button class="vb-mic-toggle" id="voice-bar-mic-toggle" onclick="SpeakMode.toggle()" title="Switch to speak mode">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="9" y="2" width="6" height="11" rx="3"/><path d="M5 10a7 7 0 0014 0"/><line x1="12" y1="19" x2="12" y2="22"/></svg>
              </button>
            </div>
          </div>
        </div>
        <div class="speak-mode-overlay hidden" id="speak-mode-overlay">
          <div class="speak-orb-container" onclick="SpeakMode.onOrbTap()">
            <div class="speak-orb">
              <div class="speak-orb-glow"></div>
              <div class="speak-orb-inner">
                <div class="speak-waveform" id="speak-waveform">
                  <span></span><span></span><span></span><span></span><span></span><span></span><span></span>
                </div>
              </div>
            </div>
          </div>
          <div class="speak-transcript" id="speak-transcript">Tap to speak</div>
          <div class="speak-bottom">
            <div class="speak-bottom-left">
              <button class="vb-icon-btn hidden" id="speak-stop-btn" onclick="stopAll()" title="Stop tutor">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>
              </button>
              <button class="vb-icon-btn hidden" id="speak-pause-btn" onclick="togglePause()" title="Pause tutor">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>
              </button>
              <button class="vb-icon-btn hidden" id="speak-resume-btn" onclick="togglePause()" title="Resume tutor">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="6,4 20,12 6,20"/></svg>
              </button>
              <button class="speak-keyboard-btn" id="speak-keyboard-btn" onclick="SpeakMode.exit()" title="Switch to typing">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="4" width="20" height="14" rx="2"/><line x1="6" y1="8" x2="6" y2="8" stroke-width="2" stroke-linecap="round"/><line x1="10" y1="8" x2="10" y2="8" stroke-width="2" stroke-linecap="round"/><line x1="14" y1="8" x2="14" y2="8" stroke-width="2" stroke-linecap="round"/><line x1="18" y1="8" x2="18" y2="8" stroke-width="2" stroke-linecap="round"/><line x1="6" y1="12" x2="6" y2="12" stroke-width="2" stroke-linecap="round"/><line x1="10" y1="12" x2="10" y2="12" stroke-width="2" stroke-linecap="round"/><line x1="14" y1="12" x2="14" y2="12" stroke-width="2" stroke-linecap="round"/><line x1="18" y1="12" x2="18" y2="12" stroke-width="2" stroke-linecap="round"/><line x1="8" y1="16" x2="16" y2="16"/></svg>
                <span>Type</span>
              </button>
            </div>
            <div class="speak-bottom-right">
              <button class="speak-mic-active" id="speak-mic-btn" onclick="SpeakMode.onOrbTap()" title="Tap to speak">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="9" y="2" width="6" height="11" rx="3"/><path d="M5 10a7 7 0 0014 0"/><line x1="12" y1="19" x2="12" y2="22"/></svg>
              </button>
            </div>
          </div>
        </div>
```

This replaces lines 1212-1219 (from `<div class="vb-bottom-right">` through the closing `</div>` of `#voice-bar-main`).

- [ ] **Step 2: Verify HTML is valid**

Open the file and visually verify the nesting is correct. The structure should be:
```
#voice-mic-float
  #vb-progress
  #vb-status
  #voice-bar-main          ← textarea and controls (type mode)
  #speak-mode-overlay      ← orb and controls (speak mode, hidden by default)
```

- [ ] **Step 3: Commit**

```bash
git add frontend/index.html
git commit -m "feat(speak-mode): add mic toggle button and speak mode overlay HTML"
```

---

### Task 3: Add Speak Mode CSS

Add all styles for the speak mode overlay, orb, waveform, color states, and transitions.

**Files:**
- Modify: `frontend/styles.css` (append after line 7713)

- [ ] **Step 1: Add all speak mode styles**

Append the following CSS at the end of `frontend/styles.css`:

```css
/* ═══ Speak Mode ═══ */

/* Mic toggle button in type mode bottom row */
.vb-mic-toggle {
  background: none;
  border: 1px solid rgba(255,255,255,.12);
  border-radius: 8px;
  color: rgba(255,255,255,.55);
  cursor: pointer;
  padding: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color .15s, border-color .15s, background .15s;
}
.vb-mic-toggle:hover {
  color: #34d399;
  border-color: rgba(52,211,153,.3);
  background: rgba(52,211,153,.08);
}

/* Hide textarea when speak mode is active */
.voice-bar-wrap.speak-active #voice-bar-main {
  display: none;
}

/* Speak mode overlay — sits inside voice-bar-wrap, replaces textarea */
.speak-mode-overlay {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 16px 12px;
  gap: 12px;
  width: 100%;
}
.speak-mode-overlay.hidden {
  display: none !important;
}

/* Show overlay when speak-active */
.voice-bar-wrap.speak-active .speak-mode-overlay {
  display: flex;
}

/* ── Orb ── */
.speak-orb-container {
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 96px;
  height: 96px;
  position: relative;
}
.speak-orb {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform .2s ease;
}
.speak-orb-container:hover .speak-orb {
  transform: scale(1.06);
}
.speak-orb-glow {
  position: absolute;
  inset: -12px;
  border-radius: 50%;
  transition: box-shadow .4s ease, opacity .4s ease;
}
.speak-orb-inner {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  transition: background .4s ease, border-color .4s ease;
}

/* ── Orb color states ── */

/* Idle: warm amber */
.speak-mode-overlay.speak-idle .speak-orb-glow {
  box-shadow: 0 0 30px 8px rgba(201,184,150,.5);
  opacity: 1;
}
.speak-mode-overlay.speak-idle .speak-orb-inner {
  background: rgba(201,184,150,.3);
  border: 1.5px solid rgba(201,184,150,.35);
}

/* Listening: green */
.speak-mode-overlay.speak-listening .speak-orb-glow {
  box-shadow: 0 0 35px 10px rgba(52,211,153,.6);
  opacity: 1;
}
.speak-mode-overlay.speak-listening .speak-orb-inner {
  background: rgba(52,211,153,.35);
  border: 1.5px solid rgba(52,211,153,.45);
}

/* Tutor responding: purple */
.speak-mode-overlay.speak-tutor .speak-orb-glow {
  box-shadow: 0 0 35px 10px rgba(139,92,246,.6);
  opacity: 1;
}
.speak-mode-overlay.speak-tutor .speak-orb-inner {
  background: rgba(139,92,246,.35);
  border: 1.5px solid rgba(139,92,246,.45);
}

/* Tutor aura — pulse */
.speak-mode-overlay.speak-tutor .speak-orb::after {
  content: '';
  position: absolute;
  inset: -18px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(139,92,246,.2) 0%, transparent 70%);
  animation: speak-tutor-aura 2s ease-in-out infinite;
  pointer-events: none;
}
@keyframes speak-tutor-aura {
  0%, 100% { transform: scale(1); opacity: .5; }
  50% { transform: scale(1.15); opacity: .8; }
}

/* ── Waveform bars inside orb ── */
.speak-waveform {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 3px;
  height: 40px;
}
.speak-waveform span {
  display: block;
  width: 4px;
  height: 8px;
  border-radius: 2px;
  background: rgba(255,255,255,.6);
  transition: height .08s ease;
}

/* Idle CSS animation fallback */
.speak-mode-overlay.speak-idle .speak-waveform span {
  animation: speak-idle-pulse 2s ease-in-out infinite;
}
.speak-mode-overlay.speak-idle .speak-waveform span:nth-child(1) { animation-delay: 0s; }
.speak-mode-overlay.speak-idle .speak-waveform span:nth-child(2) { animation-delay: .15s; }
.speak-mode-overlay.speak-idle .speak-waveform span:nth-child(3) { animation-delay: .3s; }
.speak-mode-overlay.speak-idle .speak-waveform span:nth-child(4) { animation-delay: .45s; }
.speak-mode-overlay.speak-idle .speak-waveform span:nth-child(5) { animation-delay: .3s; }
.speak-mode-overlay.speak-idle .speak-waveform span:nth-child(6) { animation-delay: .15s; }
.speak-mode-overlay.speak-idle .speak-waveform span:nth-child(7) { animation-delay: 0s; }
@keyframes speak-idle-pulse {
  0%, 100% { height: 8px; opacity: .5; }
  50% { height: 18px; opacity: .8; }
}

/* When JS drives waveform bars, disable CSS animation */
.speak-waveform.js-driven span {
  animation: none !important;
}

/* Tutor state CSS pulse */
.speak-mode-overlay.speak-tutor .speak-waveform span {
  animation: speak-tutor-pulse 2.5s ease-in-out infinite;
}
.speak-mode-overlay.speak-tutor .speak-waveform span:nth-child(1) { animation-delay: 0s; }
.speak-mode-overlay.speak-tutor .speak-waveform span:nth-child(2) { animation-delay: .2s; }
.speak-mode-overlay.speak-tutor .speak-waveform span:nth-child(3) { animation-delay: .4s; }
.speak-mode-overlay.speak-tutor .speak-waveform span:nth-child(4) { animation-delay: .6s; }
.speak-mode-overlay.speak-tutor .speak-waveform span:nth-child(5) { animation-delay: .4s; }
.speak-mode-overlay.speak-tutor .speak-waveform span:nth-child(6) { animation-delay: .2s; }
.speak-mode-overlay.speak-tutor .speak-waveform span:nth-child(7) { animation-delay: 0s; }
@keyframes speak-tutor-pulse {
  0%, 100% { height: 8px; opacity: .4; }
  50% { height: 14px; opacity: .7; }
}

/* ── Transcript text below orb ── */
.speak-transcript {
  font-size: 13px;
  color: rgba(255,255,255,.65);
  text-align: center;
  min-height: 20px;
  max-width: 90%;
  line-height: 1.4;
  word-break: break-word;
}

/* ── Bottom controls ── */
.speak-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 0 4px;
}
.speak-bottom-left {
  display: flex;
  align-items: center;
  gap: 6px;
}
.speak-bottom-right {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* Keyboard button */
.speak-keyboard-btn {
  background: none;
  border: 1px solid rgba(255,255,255,.12);
  border-radius: 8px;
  color: rgba(255,255,255,.55);
  cursor: pointer;
  padding: 5px 10px;
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  transition: color .15s, border-color .15s;
}
.speak-keyboard-btn:hover {
  color: rgba(255,255,255,.85);
  border-color: rgba(255,255,255,.25);
}

/* Mic active button (in speak mode bottom-right) */
.speak-mic-active {
  background: none;
  border: 1.5px solid rgba(52,211,153,.3);
  border-radius: 50%;
  color: #34d399;
  cursor: pointer;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color .2s, box-shadow .2s, background .2s;
}
.speak-mic-active:hover {
  border-color: rgba(52,211,153,.5);
  background: rgba(52,211,153,.1);
}

/* Pulsing ring when actively listening */
.speak-mic-active.listening {
  border-color: #34d399;
  box-shadow: 0 0 0 3px rgba(52,211,153,.2);
  animation: speak-mic-pulse 1.5s ease-in-out infinite;
}
@keyframes speak-mic-pulse {
  0%, 100% { box-shadow: 0 0 0 3px rgba(52,211,153,.2); }
  50% { box-shadow: 0 0 0 6px rgba(52,211,153,.1); }
}

/* Subtitle bar dynamic positioning — JS drives bottom via getBoundingClientRect */
/* Smooth transition when voice bar height changes */
#voice-subtitle-bar {
  transition: bottom .2s ease;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/styles.css
git commit -m "feat(speak-mode): add speak mode CSS — orb, waveform, color states, transitions"
```

---

### Task 4: Add SpeakMode IIFE Module

Add the core `SpeakMode` module to `app.js`. This module manages the tap-to-start, VAD-to-end flow with two independent states: `_active` (UI mode) and `_listening` (mic/Scribe active).

**Files:**
- Modify: `frontend/app.js:811` (add `inputMode` to state)
- Modify: `frontend/app.js` (add SpeakMode IIFE after line ~1331, after `window.scribeStop = scribeStop;`)

- [ ] **Step 1: Add inputMode to state object**

In `frontend/app.js`, find line 811 (`isStreaming: false,`) and add `inputMode` before it:

```javascript
  // Input mode: 'type' (default textarea) or 'speak' (tap-to-talk)
  inputMode: 'type',

  // Streaming
  isStreaming: false,
```

- [ ] **Step 2: Add SpeakMode IIFE module**

After the line `window.scribeStop = scribeStop;` (around line 1331), add the entire SpeakMode module:

```javascript
// ── Speak Mode: Tap-to-Start, VAD-to-End ──────────────────────
// Two independent states:
//   _active   = speak mode UI is showing (orb replaces textarea)
//   _listening = mic is on, Scribe WS is open, audio being captured
// _active && !_listening = idle orb ("Tap to speak")
// _active && _listening  = green waveform, capturing audio

var SpeakMode = (() => {
  var _active = false;
  var _listening = false;
  var _scribeWs = null;
  var _micStream = null;
  var _audioCtx = null;
  var _analyser = null;
  var _scriptNode = null;
  var _animFrameId = null;
  var _committed = '';
  var _partial = '';
  var _submitTimer = null;
  var _tapDebounce = 0;

  function isActive() { return _active; }
  function isListening() { return _listening; }

  function toggle() {
    if (_active) exit();
    else enter();
  }

  async function enter() {
    if (_active) return;

    // Stop existing browser Scribe if running
    if (_scribe && _scribe.active) scribeStop();

    // Request mic permission upfront (keeps stream for reuse)
    var stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true }
      });
    } catch (err) {
      console.warn('[SpeakMode] Mic permission denied:', err);
      _showToast('Microphone access required for speak mode');
      return;
    }

    _micStream = stream;
    _active = true;
    state.inputMode = 'speak';

    // Transform UI — show orb, hide textarea
    var wrap = document.getElementById('voice-mic-float');
    if (wrap) wrap.classList.add('speak-active');
    var overlay = document.getElementById('speak-mode-overlay');
    if (overlay) overlay.classList.remove('hidden');
    _setOverlayState('speak-idle');
    _updateTranscript('Tap to speak');

    console.log('[SpeakMode] Entered speak mode (mic idle)');
  }

  function exit() {
    if (!_active) return;

    // Stop listening if active
    if (_listening) stopListening();

    _active = false;
    state.inputMode = 'type';

    // Release mic stream
    if (_micStream) {
      _micStream.getTracks().forEach(function(t) { t.stop(); });
      _micStream = null;
    }

    // Clean up audio context
    if (_audioCtx) {
      try { _audioCtx.close(); } catch (e) {}
      _audioCtx = null;
      _analyser = null;
      _scriptNode = null;
    }

    // Restore UI
    var wrap = document.getElementById('voice-mic-float');
    if (wrap) wrap.classList.remove('speak-active');
    var overlay = document.getElementById('speak-mode-overlay');
    if (overlay) {
      overlay.classList.remove('speak-idle', 'speak-listening', 'speak-tutor');
      overlay.classList.add('hidden');
    }

    console.log('[SpeakMode] Exited speak mode');
  }

  // Called when student taps orb or mic button
  function onOrbTap() {
    if (!_active) return;

    // Debounce rapid taps (300ms)
    var now = Date.now();
    if (now - _tapDebounce < 300) return;
    _tapDebounce = now;

    if (_listening) {
      // Already listening — cancel (don't submit)
      stopListening();
      return;
    }

    // If tutor is speaking, stop it first
    if (state.isStreaming) {
      stopAll();
    }

    startListening();
  }

  function startListening() {
    if (_listening) return;
    if (!_micStream) {
      console.warn('[SpeakMode] No mic stream — re-enter speak mode');
      _showToast('Mic disconnected — tap mic icon to restart');
      return;
    }

    _listening = true;
    _committed = '';
    _partial = '';
    if (_submitTimer) { clearTimeout(_submitTimer); _submitTimer = null; }

    // Update UI to listening state
    _setOverlayState('speak-listening');
    _updateTranscript('Listening...');
    var micBtn = document.getElementById('speak-mic-btn');
    if (micBtn) micBtn.classList.add('listening');

    // Start audio capture and Scribe connection
    _startAudioCapture(_micStream);
    _connectScribe();

    console.log('[SpeakMode] Started listening');
  }

  function stopListening() {
    if (!_listening) return;
    _listening = false;

    // Stop audio processing (keep stream open for reuse)
    _stopAudioCapture();

    // Close Scribe WebSocket
    _disconnectScribe();

    // Clear pending submit
    if (_submitTimer) { clearTimeout(_submitTimer); _submitTimer = null; }
    _committed = '';
    _partial = '';

    // Update UI back to idle
    _setOverlayState('speak-idle');
    _updateTranscript('Tap to speak');
    var micBtn = document.getElementById('speak-mic-btn');
    if (micBtn) micBtn.classList.remove('listening');
    _resetWaveformBars();

    console.log('[SpeakMode] Stopped listening');
  }

  function _setOverlayState(cls) {
    var overlay = document.getElementById('speak-mode-overlay');
    if (!overlay) return;
    overlay.classList.remove('speak-idle', 'speak-listening', 'speak-tutor');
    overlay.classList.add(cls);
  }

  function _updateTranscript(text) {
    var el = document.getElementById('speak-transcript');
    if (el) el.textContent = text;
  }

  function _showToast(msg) {
    if (typeof showToast === 'function') showToast(msg);
    else console.warn('[SpeakMode]', msg);
  }

  // ── Audio Capture ──

  function _startAudioCapture(stream) {
    if (!_audioCtx) {
      _audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
    }
    var source = _audioCtx.createMediaStreamSource(stream);

    // AnalyserNode for waveform visualization
    _analyser = _audioCtx.createAnalyser();
    _analyser.fftSize = 256;
    _analyser.smoothingTimeConstant = 0.7;
    source.connect(_analyser);

    // ScriptProcessorNode for capturing PCM16 chunks to send to Scribe
    _scriptNode = _audioCtx.createScriptProcessor(4096, 1, 1);
    _scriptNode.onaudioprocess = function(e) {
      if (!_listening || !_scribeWs || _scribeWs.readyState !== WebSocket.OPEN) return;
      var input = e.inputBuffer.getChannelData(0);
      // Convert float32 [-1,1] to int16
      var pcm16 = new Int16Array(input.length);
      for (var i = 0; i < input.length; i++) {
        var s = Math.max(-1, Math.min(1, input[i]));
        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      // Base64 encode
      var bytes = new Uint8Array(pcm16.buffer);
      var binary = '';
      for (var j = 0; j < bytes.length; j++) binary += String.fromCharCode(bytes[j]);
      var b64 = btoa(binary);
      try {
        _scribeWs.send(JSON.stringify({ type: 'audio', data: b64 }));
      } catch (err) {
        console.warn('[SpeakMode] Audio send error:', err);
      }
    };

    _analyser.connect(_scriptNode);
    _scriptNode.connect(_audioCtx.destination);

    // Start waveform animation
    var waveformEl = document.getElementById('speak-waveform');
    if (waveformEl) waveformEl.classList.add('js-driven');
    _animateWaveform();
  }

  function _stopAudioCapture() {
    // Cancel animation
    if (_animFrameId) { cancelAnimationFrame(_animFrameId); _animFrameId = null; }

    // Disconnect nodes (but keep AudioContext for reuse)
    if (_scriptNode) {
      try { _scriptNode.disconnect(); } catch (e) {}
      _scriptNode = null;
    }
    if (_analyser) {
      try { _analyser.disconnect(); } catch (e) {}
      _analyser = null;
    }

    var waveformEl = document.getElementById('speak-waveform');
    if (waveformEl) waveformEl.classList.remove('js-driven');
  }

  // ── Waveform Animation ──

  function _animateWaveform() {
    if (!_analyser || !_listening) return;
    var bars = document.querySelectorAll('#speak-waveform span');
    if (!bars.length) return;

    var dataArray = new Uint8Array(_analyser.frequencyBinCount);

    function draw() {
      if (!_listening || !_analyser) return;
      _animFrameId = requestAnimationFrame(draw);
      _analyser.getByteFrequencyData(dataArray);

      var step = Math.floor(dataArray.length / bars.length);
      for (var i = 0; i < bars.length; i++) {
        var val = dataArray[i * step] || 0;
        var h = Math.max(6, (val / 255) * 40);
        bars[i].style.height = h + 'px';
      }
    }
    draw();
  }

  function _resetWaveformBars() {
    var bars = document.querySelectorAll('#speak-waveform span');
    bars.forEach(function(b) { b.style.height = ''; });
  }

  // ── Scribe WebSocket ──

  function _connectScribe() {
    if (_scribeWs) _disconnectScribe();

    var proto = location.protocol === 'https:' ? 'wss' : 'ws';
    var token = state.wsToken || '';
    var url = proto + '://' + location.host + '/ws/scribe?token=' + encodeURIComponent(token);

    _scribeWs = new WebSocket(url);

    _scribeWs.onopen = function() {
      console.log('[SpeakMode] Scribe WS opened');
    };

    _scribeWs.onmessage = function(e) {
      var msg;
      try { msg = JSON.parse(e.data); } catch (err) { return; }

      if (msg.type === 'ready') {
        console.log('[SpeakMode] Scribe ready');
        return;
      }

      if (msg.type === 'partial') {
        _partial = msg.text || '';
        var display = _committed ? _committed + ' ' + _partial : _partial;
        _updateTranscript(display || 'Listening...');

        // Interrupt tutor if speaking and partial is substantial
        if (state.isStreaming && _partial.length > 5) {
          stopAll();
        }
        return;
      }

      if (msg.type === 'committed') {
        var text = msg.text || '';
        if (text.trim()) {
          _committed += (_committed ? ' ' : '') + text.trim();
        }
        _partial = '';
        _updateTranscript(_committed || 'Listening...');

        // Debounce: wait 500ms after last committed with no new partial before submitting
        if (_submitTimer) clearTimeout(_submitTimer);
        _submitTimer = setTimeout(function() {
          _autoSubmit();
        }, 500);
        return;
      }

      if (msg.type === 'error') {
        console.warn('[SpeakMode] Scribe error:', msg.message);
        _showToast(msg.message || 'Voice error');
        stopListening();
        return;
      }
    };

    _scribeWs.onclose = function() {
      console.log('[SpeakMode] Scribe WS closed');
      _scribeWs = null;
    };

    _scribeWs.onerror = function(err) {
      console.warn('[SpeakMode] Scribe WS error:', err);
      _scribeWs = null;
      if (_listening) {
        _showToast('Voice connection error');
        stopListening();
      }
    };
  }

  function _disconnectScribe() {
    if (_scribeWs) {
      try { _scribeWs.send(JSON.stringify({ type: 'stop' })); } catch (e) {}
      try { _scribeWs.close(); } catch (e) {}
      _scribeWs = null;
    }
  }

  function _autoSubmit() {
    var text = _committed.trim();
    _committed = '';
    _partial = '';
    _submitTimer = null;

    // Stop listening (close Scribe WS, return to idle)
    stopListening();

    if (!text) return;

    // Show what the student said
    voiceShowSubtitle('You: ' + (text.length > 60 ? text.slice(0, 60) + '...' : text));
    console.log('[SpeakMode] Auto-submit: "' + text.slice(0, 40) + '"');

    // Submit via same path as type mode
    streamADK(text);
  }

  // ── Support Check ──

  function checkSupport() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      var micToggle = document.getElementById('voice-bar-mic-toggle');
      if (micToggle) micToggle.style.display = 'none';
      return false;
    }
    return true;
  }

  // ── Visibility change: stop listening if tab loses focus ──
  document.addEventListener('visibilitychange', function() {
    if (document.hidden && _listening) {
      console.log('[SpeakMode] Tab hidden — stopping listen');
      stopListening();
    }
  });

  return {
    isActive: isActive,
    isListening: isListening,
    toggle: toggle,
    enter: enter,
    exit: exit,
    onOrbTap: onOrbTap,
    startListening: startListening,
    stopListening: stopListening,
    _setOverlayState: _setOverlayState,
    _updateTranscript: _updateTranscript,
    checkSupport: checkSupport,
  };
})();
window.SpeakMode = SpeakMode;
```

- [ ] **Step 3: Add SpeakMode.checkSupport() call on DOMContentLoaded**

Find the `DOMContentLoaded` event listener (search for `addEventListener('DOMContentLoaded'`). At the end of the callback, add:

```javascript
    if (typeof SpeakMode !== 'undefined') SpeakMode.checkSupport();
```

- [ ] **Step 4: Commit**

```bash
git add frontend/app.js
git commit -m "feat(speak-mode): add SpeakMode IIFE module with tap-to-start, VAD-to-end flow"
```

---

### Task 5: Wire Up setVoiceBarState for Speak Mode

Modify `setVoiceBarState()` to handle speak mode overlay states when `state.inputMode === 'speak'`.

**Files:**
- Modify: `frontend/app.js:19356-19444` (`setVoiceBarState` function)

- [ ] **Step 1: Add speak mode branch before the type-mode switch**

In `setVoiceBarState()`, after the line `if (_wrapEl) _wrapEl.classList.remove('euler-speaking');` (line 19390), and before the `switch (newState) {` (line 19392), add the speak mode handler block:

```javascript
  // ── Speak mode overlay state ──
  if (state.inputMode === 'speak' && typeof SpeakMode !== 'undefined' && SpeakMode.isActive()) {
    var speakStop = document.getElementById('speak-stop-btn');
    var speakPause = document.getElementById('speak-pause-btn');
    var speakResume = document.getElementById('speak-resume-btn');

    // Reset speak controls
    if (speakStop) speakStop.classList.add('hidden');
    if (speakPause) speakPause.classList.add('hidden');
    if (speakResume) speakResume.classList.add('hidden');

    switch (newState) {
      case 'idle':
        // Only set to idle if not actively listening (listening state is driven by SpeakMode)
        if (!SpeakMode.isListening()) {
          SpeakMode._setOverlayState('speak-idle');
          SpeakMode._updateTranscript('Tap to speak');
        }
        break;
      case 'thinking':
        SpeakMode._setOverlayState('speak-idle');
        SpeakMode._updateTranscript('Thinking...');
        if (speakStop) speakStop.classList.remove('hidden');
        break;
      case 'speaking':
        SpeakMode._setOverlayState('speak-tutor');
        SpeakMode._updateTranscript('Tap mic to interrupt');
        if (speakStop) speakStop.classList.remove('hidden');
        if (speakPause) speakPause.classList.remove('hidden');
        break;
      case 'paused':
        SpeakMode._setOverlayState('speak-tutor');
        SpeakMode._updateTranscript('Paused — tap mic or resume');
        if (speakResume) speakResume.classList.remove('hidden');
        break;
    }
  }
```

- [ ] **Step 2: Wrap existing switch in type-mode guard**

Wrap the existing `switch (newState) {` block (lines 19392-19443) in an `if` guard so it only runs in type mode:

```javascript
  if (state.inputMode !== 'speak') {
  switch (newState) {
    // ... existing cases unchanged ...
  }
  } // end if (state.inputMode !== 'speak')
```

- [ ] **Step 3: Add subtitle bar positioning**

After the closing brace of `setVoiceBarState()`, add a helper function to dynamically position the subtitle bar above the voice bar:

```javascript
function _positionSubtitleBar() {
  var wrap = document.getElementById('voice-mic-float');
  var bar = document.getElementById('voice-subtitle-bar');
  if (!wrap || !bar) return;
  var wrapRect = wrap.getBoundingClientRect();
  var wrapBottom = window.innerHeight - wrapRect.top;
  bar.style.bottom = (wrapBottom + 8) + 'px';
}
```

Call `_positionSubtitleBar()` at the end of `setVoiceBarState()` (just before the closing brace), and also at the end of `voiceShowSubtitle()`.

- [ ] **Step 4: Commit**

```bash
git add frontend/app.js
git commit -m "feat(speak-mode): wire setVoiceBarState for speak mode overlay states"
```

---

### Task 6: Integration Testing and Polish

Test the full end-to-end flow and fix any issues found.

**Files:**
- Possibly modify: `frontend/app.js`, `frontend/styles.css`, `frontend/index.html`

- [ ] **Step 1: Start the dev server**

Run: `cd /Users/admin/Documents/repos/euler_tutor && cd backend && source .venv/bin/activate && python -m uvicorn app.main:app --host 0.0.0.0 --port 3001 --reload --reload-dir ../backend --reload-dir ../frontend --reload-include '*.html' --reload-include '*.css' --reload-include '*.js' --app-dir .`

- [ ] **Step 2: Test type mode (default)**

1. Start a teaching session
2. Verify the voice bar shows textarea with "Your answer..." placeholder
3. Verify the mic toggle button appears in the bottom-right, next to send
4. Type a message and submit — verify tutor responds normally
5. Verify no mic is active (no browser mic permission prompt)

- [ ] **Step 3: Test entering speak mode**

1. Click the mic toggle button
2. Verify browser asks for mic permission
3. Verify textarea is replaced by the amber orb with "Tap to speak" text
4. Verify the Type/keyboard button appears in bottom-left
5. Verify the mic button appears in bottom-right
6. Verify NO audio is being captured (mic should be idle)

- [ ] **Step 4: Test tap-to-start listening**

1. Tap the orb or mic button
2. Verify orb turns green with reactive waveform
3. Verify transcript shows "Listening..."
4. Verify mic button shows pulsing green ring
5. Speak a sentence — verify waveform reacts to audio levels
6. Verify partial transcript text appears as you speak

- [ ] **Step 5: Test VAD-to-end auto-submit**

1. Speak a sentence, then stop speaking
2. Verify ElevenLabs VAD detects silence and auto-submits
3. Verify "You: {text}" appears in subtitle bar
4. Verify orb returns to amber idle state with "Tap to speak"
5. Verify mic is off (no more audio capture)
6. Verify tutor responds (orb turns purple with "Tap mic to interrupt")

- [ ] **Step 6: Test interrupt**

1. While tutor is speaking (purple orb), tap the orb or mic button
2. Verify tutor stops immediately
3. Verify mic starts listening (green orb)
4. Speak an interruption, stop speaking
5. Verify new response from tutor

- [ ] **Step 7: Test exit speak mode**

1. Click the "Type" keyboard button
2. Verify textarea returns with "Your answer..." placeholder
3. Verify orb overlay is hidden
4. Verify mic is released (no browser mic indicator)

- [ ] **Step 8: Test no ambient noise pickup**

1. Enter speak mode
2. Verify orb is idle (amber) — make noise nearby
3. Verify no text appears, no submission happens
4. Only tapping should activate the mic

- [ ] **Step 9: Fix any issues found and commit**

```bash
git add -A
git commit -m "fix(speak-mode): integration fixes from end-to-end testing"
```
