# Speak Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent speak mode to the voice bar that uses ElevenLabs Scribe for always-on STT with native VAD, replacing the textarea with an animated orb/waveform visualization.

**Architecture:** A new `SpeakMode` IIFE module in app.js manages the Scribe WebSocket, mic audio capture, waveform animation, and UI transformation. It integrates with the existing `setVoiceBarState()` and `streamADK()` functions. No backend changes needed.

**Tech Stack:** Web Audio API (`getUserMedia`, `AudioContext`, `AnalyserNode`, `ScriptProcessorNode`), WebSocket (`/ws/scribe`), CSS animations, existing ElevenLabs Scribe backend relay.

**Spec:** `docs/superpowers/specs/2026-04-24-speak-mode-design.md`

---

### Task 1: Add Speak Mode HTML Structure

**Files:**
- Modify: `frontend/index.html:1190-1219` (voice bar container)

- [ ] **Step 1: Add mic toggle button to type mode bottom row**

In `frontend/index.html`, find the `vb-bottom-right` div (line 1212) and add the mic toggle button after the send button:

```html
            <div class="vb-bottom-right">
              <button class="vb-send-btn visible" id="voice-bar-send" onclick="submitVoiceBarInput()" title="Send (Enter)">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
              </button>
              <button class="vb-mic-toggle" id="voice-bar-mic-toggle" onclick="SpeakMode.toggle()" title="Switch to speak mode">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="9" y="2" width="6" height="11" rx="3"/><path d="M5 10a7 7 0 0014 0"/><line x1="12" y1="19" x2="12" y2="22"/></svg>
              </button>
            </div>
```

- [ ] **Step 2: Add speak mode overlay container**

Add a new sibling div right after the closing `</div>` of `voice-bar-main` (after line 1218), before the closing `</div>` of `voice-mic-float`:

```html
        <div class="speak-mode-overlay hidden" id="speak-mode-overlay">
          <div class="speak-orb-container">
            <div class="speak-orb">
              <div class="speak-orb-glow"></div>
              <div class="speak-orb-inner">
                <div class="speak-waveform" id="speak-waveform">
                  <span></span><span></span><span></span><span></span><span></span><span></span><span></span>
                </div>
              </div>
            </div>
          </div>
          <div class="speak-transcript" id="speak-transcript">Listening...</div>
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
              <button class="speak-mic-active" id="speak-mic-btn" onclick="SpeakMode.exit()" title="Mic on — click to switch to typing">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="9" y="2" width="6" height="11" rx="3"/><path d="M5 10a7 7 0 0014 0"/><line x1="12" y1="19" x2="12" y2="22"/></svg>
              </button>
            </div>
          </div>
        </div>
```

- [ ] **Step 3: Verify the HTML renders**

Open the app in a browser (or reload if already open). The voice bar should look exactly the same as before, except with a small mic icon button next to the send button. The speak mode overlay is hidden. Visually confirm nothing broke.

- [ ] **Step 4: Commit**

```bash
git add frontend/index.html
git commit -m "feat(speak-mode): add HTML structure for speak mode overlay and mic toggle"
```

---

### Task 2: Add Speak Mode CSS

**Files:**
- Modify: `frontend/styles.css` (append after line ~6329, after existing voice bar styles)

- [ ] **Step 1: Add mic toggle button styles**

Append to `frontend/styles.css` after the voice bar section (after line 6329):

```css
/* ═══ Speak Mode ══════════════════════════════════════════════ */

/* Mic toggle button in type mode — sits next to send button */
.vb-mic-toggle {
  width: 32px; height: 32px; border-radius: 8px;
  background: none; border: 1px solid rgba(255,255,255,0.08);
  color: rgba(255,255,255,0.3); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.2s;
}
.vb-mic-toggle:hover {
  border-color: rgba(52,211,153,0.3);
  color: rgba(52,211,153,0.7);
  background: rgba(52,211,153,0.06);
}
.vb-mic-toggle svg { width: 16px; height: 16px; }
```

- [ ] **Step 2: Add speak mode overlay styles**

Continue appending:

```css
/* Speak mode overlay — replaces textarea when active */
.speak-mode-overlay {
  display: flex; flex-direction: column; align-items: center;
  padding: 24px 20px 16px;
  background: rgba(12,16,22,0.95);
  border: 1px solid rgba(52,211,153,0.1);
  border-radius: 22px;
  backdrop-filter: blur(16px);
  box-shadow: 0 4px 30px rgba(0,0,0,0.5);
  transition: border-color 0.3s, box-shadow 0.3s;
}
.speak-mode-overlay.hidden { display: none; }

/* When speak mode is active, hide the type mode bar */
.voice-bar-wrap.speak-active #voice-bar-main { display: none; }
.voice-bar-wrap.speak-active .speak-mode-overlay { display: flex; }
```

- [ ] **Step 3: Add orb styles**

Continue appending:

```css
/* ── Orb ── */
.speak-orb-container {
  position: relative; width: 64px; height: 64px; margin-bottom: 12px;
}
.speak-orb {
  width: 64px; height: 64px; border-radius: 50%; position: relative;
}
.speak-orb-glow {
  position: absolute; inset: -8px; border-radius: 50%;
  filter: blur(12px); opacity: 0.4;
  background: radial-gradient(circle, rgba(52,211,153,0.3), transparent);
  animation: speak-pulse-gentle 3s ease-in-out infinite;
  transition: background 0.5s, opacity 0.5s;
}
.speak-orb-inner {
  position: absolute; inset: 0; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  background: radial-gradient(circle at 40% 40%, rgba(52,211,153,0.15), rgba(52,211,153,0.03));
  border: 1px solid rgba(52,211,153,0.2);
  transition: background 0.5s, border-color 0.5s;
}

/* Orb state: idle (amber) */
.speak-mode-overlay.speak-idle .speak-orb-glow {
  background: radial-gradient(circle, rgba(201,184,150,0.3), transparent);
  animation: speak-pulse-gentle 3s ease-in-out infinite;
}
.speak-mode-overlay.speak-idle .speak-orb-inner {
  background: radial-gradient(circle at 40% 40%, rgba(201,184,150,0.15), rgba(201,184,150,0.03));
  border-color: rgba(201,184,150,0.2);
}

/* Orb state: listening (green) */
.speak-mode-overlay.speak-listening .speak-orb-glow {
  background: radial-gradient(circle, rgba(52,211,153,0.4), transparent);
  animation: speak-pulse-active 1s ease-in-out infinite;
  opacity: 0.6;
}
.speak-mode-overlay.speak-listening .speak-orb-inner {
  background: radial-gradient(circle at 40% 40%, rgba(52,211,153,0.25), rgba(52,211,153,0.05));
  border-color: rgba(52,211,153,0.35);
}

/* Orb state: tutor responding (purple) */
.speak-mode-overlay.speak-tutor .speak-orb-glow {
  background: radial-gradient(circle, rgba(139,92,246,0.4), transparent);
  animation: speak-pulse-tutor 2s ease-in-out infinite;
}
.speak-mode-overlay.speak-tutor .speak-orb-inner {
  background: radial-gradient(circle at 40% 40%, rgba(139,92,246,0.25), rgba(139,92,246,0.05));
  border-color: rgba(139,92,246,0.3);
}
.speak-mode-overlay.speak-tutor {
  border-color: rgba(139,92,246,0.2);
}

@keyframes speak-pulse-gentle {
  0%, 100% { transform: scale(1); opacity: 0.3; }
  50% { transform: scale(1.15); opacity: 0.5; }
}
@keyframes speak-pulse-active {
  0%, 100% { transform: scale(1); opacity: 0.4; }
  50% { transform: scale(1.2); opacity: 0.7; }
}
@keyframes speak-pulse-tutor {
  0%, 100% { transform: scale(1); opacity: 0.3; }
  50% { transform: scale(1.1); opacity: 0.5; }
}
```

- [ ] **Step 4: Add waveform, transcript, and controls styles**

Continue appending:

```css
/* ── Waveform bars ── */
.speak-waveform {
  display: flex; gap: 3px; align-items: center; height: 24px;
}
.speak-waveform span {
  width: 3px; border-radius: 2px; background: rgba(201,184,150,0.3);
  transition: height 0.1s ease, background 0.3s;
}
.speak-waveform span:nth-child(1) { height: 6px; }
.speak-waveform span:nth-child(2) { height: 10px; }
.speak-waveform span:nth-child(3) { height: 14px; }
.speak-waveform span:nth-child(4) { height: 10px; }
.speak-waveform span:nth-child(5) { height: 8px; }
.speak-waveform span:nth-child(6) { height: 12px; }
.speak-waveform span:nth-child(7) { height: 6px; }

/* Listening: green bars with CSS animation fallback */
.speak-mode-overlay.speak-listening .speak-waveform span {
  background: #34d399;
  animation: speak-wave 0.8s ease-in-out infinite;
}
.speak-mode-overlay.speak-listening .speak-waveform span:nth-child(1) { animation-delay: 0s; }
.speak-mode-overlay.speak-listening .speak-waveform span:nth-child(2) { animation-delay: 0.1s; }
.speak-mode-overlay.speak-listening .speak-waveform span:nth-child(3) { animation-delay: 0.2s; }
.speak-mode-overlay.speak-listening .speak-waveform span:nth-child(4) { animation-delay: 0.3s; }
.speak-mode-overlay.speak-listening .speak-waveform span:nth-child(5) { animation-delay: 0.15s; }
.speak-mode-overlay.speak-listening .speak-waveform span:nth-child(6) { animation-delay: 0.25s; }
.speak-mode-overlay.speak-listening .speak-waveform span:nth-child(7) { animation-delay: 0.05s; }

/* Tutor responding: purple bars, slower animation */
.speak-mode-overlay.speak-tutor .speak-waveform span {
  background: #8b5cf6;
  animation: speak-wave 1.5s ease-in-out infinite;
}
.speak-mode-overlay.speak-tutor .speak-waveform span:nth-child(1) { animation-delay: 0s; }
.speak-mode-overlay.speak-tutor .speak-waveform span:nth-child(2) { animation-delay: 0.15s; }
.speak-mode-overlay.speak-tutor .speak-waveform span:nth-child(3) { animation-delay: 0.3s; }
.speak-mode-overlay.speak-tutor .speak-waveform span:nth-child(4) { animation-delay: 0.2s; }
.speak-mode-overlay.speak-tutor .speak-waveform span:nth-child(5) { animation-delay: 0.1s; }
.speak-mode-overlay.speak-tutor .speak-waveform span:nth-child(6) { animation-delay: 0.25s; }
.speak-mode-overlay.speak-tutor .speak-waveform span:nth-child(7) { animation-delay: 0.35s; }

@keyframes speak-wave {
  0%, 100% { transform: scaleY(0.4); }
  50% { transform: scaleY(1.2); }
}

/* ── Transcript text ── */
.speak-transcript {
  font-size: 14px; color: rgba(255,255,255,0.35); text-align: center;
  min-height: 20px; max-width: 90%; line-height: 1.4;
  font-family: var(--font-sans); transition: color 0.2s;
}
.speak-mode-overlay.speak-listening .speak-transcript {
  color: var(--text);
}

/* ── Bottom controls ── */
.speak-bottom {
  display: flex; justify-content: space-between; align-items: center;
  width: 100%; margin-top: 14px; padding-top: 12px;
  border-top: 1px solid rgba(255,255,255,0.04);
}
.speak-bottom-left { display: flex; align-items: center; gap: 4px; }
.speak-bottom-right { display: flex; align-items: center; }

.speak-keyboard-btn {
  background: none; border: 1px solid rgba(255,255,255,0.08);
  color: rgba(255,255,255,0.3); cursor: pointer;
  padding: 4px 10px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  gap: 5px; font-size: 12px; font-family: var(--font-sans);
  transition: all 0.2s;
}
.speak-keyboard-btn:hover {
  border-color: rgba(255,255,255,0.15); color: rgba(255,255,255,0.5);
  background: rgba(255,255,255,0.03);
}
.speak-keyboard-btn svg { width: 14px; height: 14px; }

.speak-mic-active {
  width: 32px; height: 32px; border-radius: 8px;
  background: rgba(52,211,153,0.12); border: 1px solid rgba(52,211,153,0.25);
  color: #34d399; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.2s;
}
.speak-mic-active:hover {
  background: rgba(52,211,153,0.2); border-color: rgba(52,211,153,0.4);
}
.speak-mic-active svg { width: 16px; height: 16px; }

/* Euler speaking aura in speak mode */
.speak-mode-overlay.speak-tutor::before {
  content: '';
  position: absolute; inset: -3px; border-radius: 24px;
  background: linear-gradient(135deg, rgba(139,92,246,0.12), rgba(139,92,246,0.04));
  border: 1px solid rgba(139,92,246,0.15);
  z-index: -1;
  animation: speak-aura-pulse 2s ease-in-out infinite;
  pointer-events: none;
}
@keyframes speak-aura-pulse {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}
```

- [ ] **Step 5: Verify styles render**

Reload the app. The mic toggle button should appear next to the send button with subtle styling. Hover should show green tint.

- [ ] **Step 6: Commit**

```bash
git add frontend/styles.css
git commit -m "feat(speak-mode): add CSS for orb, waveform, transcript, and mode controls"
```

---

### Task 3: Implement SpeakMode Module — Core State and UI Toggle

**Files:**
- Modify: `frontend/app.js` (insert new module after the existing Scribe code, after line 1331)

- [ ] **Step 1: Add the SpeakMode IIFE skeleton with enter/exit/toggle**

Insert after line 1331 in `frontend/app.js` (after the `window.scribeStop = scribeStop;` line):

```javascript
// ═══ Speak Mode — Always-On Voice Input via ElevenLabs Scribe ═══
var SpeakMode = (() => {
  var _active = false;
  var _scribeWs = null;
  var _micStream = null;
  var _audioCtx = null;
  var _analyser = null;
  var _scriptNode = null;
  var _animFrameId = null;
  var _committed = '';
  var _partial = '';
  var _submitTimer = null;
  var _reconnectAttempts = 0;
  var _maxReconnectAttempts = 3;

  function isActive() { return _active; }

  function toggle() {
    if (_active) exit();
    else enter();
  }

  async function enter() {
    if (_active) return;

    // Stop existing browser Scribe if running
    if (_scribe && _scribe.active) scribeStop();

    // Request mic permission
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
    _committed = '';
    _partial = '';
    _reconnectAttempts = 0;
    state.inputMode = 'speak';

    // Transform UI
    var wrap = document.getElementById('voice-mic-float');
    if (wrap) wrap.classList.add('speak-active');
    _setOverlayState('speak-idle');
    _updateTranscript('Listening...');

    // Start audio capture and Scribe connection
    _startAudioCapture(stream);
    _connectScribe();

    console.log('[SpeakMode] Entered speak mode');
  }

  function exit() {
    if (!_active) return;
    _active = false;
    state.inputMode = 'type';

    // Stop audio capture
    _stopAudioCapture();

    // Close Scribe WebSocket
    _disconnectScribe();

    // Restore UI
    var wrap = document.getElementById('voice-mic-float');
    if (wrap) wrap.classList.remove('speak-active');
    var overlay = document.getElementById('speak-mode-overlay');
    if (overlay) {
      overlay.classList.remove('speak-idle', 'speak-listening', 'speak-tutor');
    }

    // Clear any pending submit
    if (_submitTimer) { clearTimeout(_submitTimer); _submitTimer = null; }
    _committed = '';
    _partial = '';

    console.log('[SpeakMode] Exited speak mode');
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
    // Use existing toast system if available, else console
    if (typeof showToast === 'function') showToast(msg);
    else console.warn('[SpeakMode]', msg);
  }

  // Placeholder stubs — implemented in subsequent tasks
  function _startAudioCapture(stream) {}
  function _stopAudioCapture() {}
  function _connectScribe() {}
  function _disconnectScribe() {}

  return {
    isActive: isActive,
    toggle: toggle,
    enter: enter,
    exit: exit,
    // Expose for setVoiceBarState integration
    _setOverlayState: _setOverlayState,
    _updateTranscript: _updateTranscript,
  };
})();
window.SpeakMode = SpeakMode;
```

- [ ] **Step 2: Add `state.inputMode` initialization**

Find the state initialization object in `app.js` (search for where `state.isStreaming` is initialized). Add `inputMode: 'type'` to the state object. This will be near the top of the state object definition.

- [ ] **Step 3: Verify toggle works**

Reload the app. Click the mic toggle button. The textarea should disappear and the speak mode overlay should appear (idle state, amber orb). Click the "Type" button or the green mic button in speak mode. The textarea should reappear. The Scribe connection won't work yet (stubs), but the UI toggle should be clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/app.js
git commit -m "feat(speak-mode): add SpeakMode module skeleton with UI toggle"
```

---

### Task 4: Implement Audio Capture and Waveform Animation

**Files:**
- Modify: `frontend/app.js` (replace `_startAudioCapture` and `_stopAudioCapture` stubs in SpeakMode)

- [ ] **Step 1: Implement `_startAudioCapture`**

Replace the `_startAudioCapture` stub inside the SpeakMode IIFE:

```javascript
  function _startAudioCapture(stream) {
    _audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
    var source = _audioCtx.createMediaStreamSource(stream);

    // AnalyserNode for waveform visualization
    _analyser = _audioCtx.createAnalyser();
    _analyser.fftSize = 256;
    _analyser.smoothingTimeConstant = 0.7;
    source.connect(_analyser);

    // ScriptProcessorNode for capturing PCM16 chunks to send to Scribe
    // Buffer size 4096 at 16kHz = ~256ms chunks
    _scriptNode = _audioCtx.createScriptProcessor(4096, 1, 1);
    _scriptNode.onaudioprocess = function(e) {
      if (!_active || !_scribeWs || _scribeWs.readyState !== WebSocket.OPEN) return;
      var input = e.inputBuffer.getChannelData(0);
      // Convert float32 to int16
      var pcm16 = new Int16Array(input.length);
      for (var i = 0; i < input.length; i++) {
        var s = Math.max(-1, Math.min(1, input[i]));
        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      // Base64 encode and send
      var bytes = new Uint8Array(pcm16.buffer);
      var b64 = '';
      var chunk = 8192;
      for (var j = 0; j < bytes.length; j += chunk) {
        b64 += String.fromCharCode.apply(null, bytes.subarray(j, Math.min(j + chunk, bytes.length)));
      }
      b64 = btoa(b64);
      try {
        _scribeWs.send(JSON.stringify({ type: 'audio', data: b64 }));
      } catch (err) {
        console.warn('[SpeakMode] Audio send error:', err);
      }
    };
    source.connect(_scriptNode);
    _scriptNode.connect(_audioCtx.destination); // Required for ScriptProcessor to fire

    // Start waveform animation loop
    _animateWaveform();
  }
```

- [ ] **Step 2: Implement `_stopAudioCapture`**

Replace the `_stopAudioCapture` stub:

```javascript
  function _stopAudioCapture() {
    if (_animFrameId) { cancelAnimationFrame(_animFrameId); _animFrameId = null; }
    if (_scriptNode) { try { _scriptNode.disconnect(); } catch(e) {} _scriptNode = null; }
    if (_analyser) { try { _analyser.disconnect(); } catch(e) {} _analyser = null; }
    if (_audioCtx) { try { _audioCtx.close(); } catch(e) {} _audioCtx = null; }
    if (_micStream) {
      _micStream.getTracks().forEach(function(t) { t.stop(); });
      _micStream = null;
    }
    // Reset waveform bars to default heights
    _resetWaveformBars();
  }
```

- [ ] **Step 3: Implement `_animateWaveform`**

Add this function inside the SpeakMode IIFE:

```javascript
  function _animateWaveform() {
    if (!_active || !_analyser) return;
    var bars = document.querySelectorAll('#speak-waveform span');
    if (!bars.length) { _animFrameId = requestAnimationFrame(_animateWaveform); return; }

    var dataArray = new Uint8Array(_analyser.frequencyBinCount);
    _analyser.getByteFrequencyData(dataArray);

    // Map frequency bins to 7 bars
    var binCount = _analyser.frequencyBinCount;
    var binsPerBar = Math.floor(binCount / bars.length);
    var hasSignal = false;

    for (var i = 0; i < bars.length; i++) {
      var sum = 0;
      for (var j = 0; j < binsPerBar; j++) {
        sum += dataArray[i * binsPerBar + j];
      }
      var avg = sum / binsPerBar;
      if (avg > 15) hasSignal = true;
      // Map 0-255 to 4px-28px height
      var h = Math.max(4, (avg / 255) * 28);
      bars[i].style.height = h + 'px';
    }

    // Update overlay state based on audio level (only when not in tutor state)
    var overlay = document.getElementById('speak-mode-overlay');
    if (overlay && !overlay.classList.contains('speak-tutor')) {
      if (hasSignal) {
        if (!overlay.classList.contains('speak-listening')) _setOverlayState('speak-listening');
      } else {
        if (!overlay.classList.contains('speak-idle')) _setOverlayState('speak-idle');
      }
    }

    _animFrameId = requestAnimationFrame(_animateWaveform);
  }

  function _resetWaveformBars() {
    var bars = document.querySelectorAll('#speak-waveform span');
    var defaults = [6, 10, 14, 10, 8, 12, 6];
    bars.forEach(function(bar, i) { bar.style.height = (defaults[i] || 6) + 'px'; });
  }
```

- [ ] **Step 4: Verify waveform animation**

Reload the app. Enter speak mode. The orb should appear amber (idle). Speak into the mic. The waveform bars should react to your voice level in real-time, and the orb state should shift between idle (amber) and listening (green) based on audio signal presence.

- [ ] **Step 5: Commit**

```bash
git add frontend/app.js
git commit -m "feat(speak-mode): implement mic audio capture and reactive waveform animation"
```

---

### Task 5: Implement Scribe WebSocket Connection and Transcript Handling

**Files:**
- Modify: `frontend/app.js` (replace `_connectScribe` and `_disconnectScribe` stubs in SpeakMode)

- [ ] **Step 1: Implement `_connectScribe`**

Replace the `_connectScribe` stub inside the SpeakMode IIFE:

```javascript
  function _connectScribe() {
    if (_scribeWs && _scribeWs.readyState === WebSocket.OPEN) return;

    var proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    var token = typeof AuthManager !== 'undefined' ? AuthManager.getToken() : '';
    var url = proto + '//' + location.host + '/ws/scribe?token=' + encodeURIComponent(token);

    console.log('[SpeakMode] Connecting to Scribe...');
    _scribeWs = new WebSocket(url);

    _scribeWs.onopen = function() {
      console.log('[SpeakMode] Scribe WS open');
      _reconnectAttempts = 0;
    };

    _scribeWs.onmessage = function(evt) {
      var msg;
      try { msg = JSON.parse(evt.data); } catch(e) { return; }

      if (msg.type === 'ready') {
        console.log('[SpeakMode] Scribe session ready');
        return;
      }

      if (msg.type === 'partial') {
        _partial = msg.text || '';
        var display = _committed ? _committed + ' ' + _partial : _partial;
        _updateTranscript(display || 'Listening...');

        // Interrupt tutor if speaking and we detect meaningful speech
        if (state.isStreaming && _partial.length > 5) {
          console.log('[SpeakMode] Interrupting tutor — speech detected');
          stopAll();
        }
        return;
      }

      if (msg.type === 'committed') {
        var text = msg.text || '';
        if (!text.trim()) return;

        _committed += (_committed ? ' ' : '') + text;
        _partial = '';
        _updateTranscript(_committed);

        // Interrupt tutor if still streaming
        if (state.isStreaming) {
          console.log('[SpeakMode] Interrupting tutor — committed transcript');
          stopAll();
        }

        // Auto-submit: debounce 500ms after last committed (in case of multi-chunk utterance)
        if (_submitTimer) clearTimeout(_submitTimer);
        _submitTimer = setTimeout(function() {
          _autoSubmit();
        }, 500);
        return;
      }

      if (msg.type === 'error') {
        console.warn('[SpeakMode] Scribe error:', msg.message);
        _showToast('Voice recognition error — retrying...');
        _reconnect();
        return;
      }
    };

    _scribeWs.onclose = function(evt) {
      console.log('[SpeakMode] Scribe WS closed:', evt.code);
      if (_active) _reconnect();
    };

    _scribeWs.onerror = function(err) {
      console.warn('[SpeakMode] Scribe WS error:', err);
    };
  }
```

- [ ] **Step 2: Implement `_disconnectScribe`**

Replace the `_disconnectScribe` stub:

```javascript
  function _disconnectScribe() {
    if (_scribeWs) {
      try { _scribeWs.send(JSON.stringify({ type: 'stop' })); } catch(e) {}
      try { _scribeWs.onclose = null; _scribeWs.close(); } catch(e) {}
      _scribeWs = null;
    }
  }
```

- [ ] **Step 3: Implement `_autoSubmit` and `_reconnect`**

Add these functions inside the SpeakMode IIFE:

```javascript
  function _autoSubmit() {
    var text = _committed.trim();
    if (!text || state.isStreaming) return;

    console.log('[SpeakMode] Auto-submit: "' + text.slice(0, 50) + '"');

    // Show what user said in subtitle bar
    voiceShowSubtitle('You: ' + (text.length > 60 ? text.slice(0, 60) + '...' : text));

    // Submit through the standard pipeline
    streamADK(text);

    // Reset transcript
    _committed = '';
    _partial = '';
    _updateTranscript('');
  }

  function _reconnect() {
    if (!_active) return;
    _reconnectAttempts++;
    if (_reconnectAttempts > _maxReconnectAttempts) {
      console.warn('[SpeakMode] Max reconnect attempts reached — falling back to type mode');
      _showToast('Voice connection lost — switched to typing');
      exit();
      return;
    }
    var delay = Math.min(1000 * Math.pow(2, _reconnectAttempts - 1), 5000);
    console.log('[SpeakMode] Reconnecting in ' + delay + 'ms (attempt ' + _reconnectAttempts + ')');
    setTimeout(function() {
      if (_active) _connectScribe();
    }, delay);
  }
```

- [ ] **Step 4: Expose `_autoSubmit` in return object (needed for setVoiceBarState integration later)**

Update the SpeakMode return object to include the new internal methods needed externally:

```javascript
  return {
    isActive: isActive,
    toggle: toggle,
    enter: enter,
    exit: exit,
    _setOverlayState: _setOverlayState,
    _updateTranscript: _updateTranscript,
  };
```

(No change needed -- `_setOverlayState` and `_updateTranscript` are already exposed.)

- [ ] **Step 5: Verify end-to-end speak mode flow**

Reload the app. Enter speak mode. Speak a sentence. Verify:
1. Live transcription appears below the orb
2. When you stop speaking, ElevenLabs VAD triggers `committed_transcript`
3. Text auto-submits to `streamADK`
4. Tutor starts responding

- [ ] **Step 6: Commit**

```bash
git add frontend/app.js
git commit -m "feat(speak-mode): implement Scribe WebSocket connection and auto-submit on VAD"
```

---

### Task 6: Integrate SpeakMode with Voice Bar State Machine

**Files:**
- Modify: `frontend/app.js:19356-19444` (`setVoiceBarState` function)

- [ ] **Step 1: Add speak mode awareness to `setVoiceBarState`**

In the `setVoiceBarState` function (line 19356), add a speak mode branch at the top of the function body, right after the existing reset logic (after line 19391, before the `switch` statement):

```javascript
  // ── Speak mode overlay state ──
  if (state.inputMode === 'speak' && SpeakMode.isActive()) {
    var speakOverlay = document.getElementById('speak-mode-overlay');
    var speakStop = document.getElementById('speak-stop-btn');
    var speakPause = document.getElementById('speak-pause-btn');
    var speakResume = document.getElementById('speak-resume-btn');

    // Reset speak controls
    if (speakStop) speakStop.classList.add('hidden');
    if (speakPause) speakPause.classList.add('hidden');
    if (speakResume) speakResume.classList.add('hidden');

    switch (newState) {
      case 'idle':
        SpeakMode._setOverlayState('speak-idle');
        SpeakMode._updateTranscript('Listening...');
        break;
      case 'thinking':
        SpeakMode._setOverlayState('speak-idle');
        SpeakMode._updateTranscript('Thinking...');
        if (speakStop) speakStop.classList.remove('hidden');
        break;
      case 'speaking':
        SpeakMode._setOverlayState('speak-tutor');
        SpeakMode._updateTranscript('Speak to interrupt...');
        if (speakStop) speakStop.classList.remove('hidden');
        if (speakPause) speakPause.classList.remove('hidden');
        break;
      case 'paused':
        SpeakMode._setOverlayState('speak-tutor');
        SpeakMode._updateTranscript('Paused — speak or tap resume');
        if (speakResume) speakResume.classList.remove('hidden');
        break;
    }
    // Still run the normal state logic below for non-UI state tracking
    // (progress bar, safety timeout, etc.) but skip field/button manipulation
    // since those elements are hidden in speak mode.
  }
```

- [ ] **Step 2: Guard type-mode-specific UI updates**

Wrap the `switch (newState)` block's field-specific operations (lines 19392-19443) so they only run in type mode. Find the existing `switch (newState) {` and wrap it:

```javascript
  if (state.inputMode !== 'speak') {
    switch (newState) {
      // ... existing cases unchanged ...
    }
  }
```

This ensures the type mode textarea, send button, and mic button manipulations don't interfere with speak mode.

- [ ] **Step 3: Verify state transitions in speak mode**

Reload the app. Enter speak mode. Submit an answer by speaking. Verify:
1. On submit: overlay transitions to `speak-idle` with "Thinking..." text
2. When tutor starts speaking: overlay transitions to `speak-tutor` (purple orb, "Speak to interrupt...", stop/pause visible)
3. When tutor finishes: overlay returns to `speak-idle` with "Listening..."
4. Speaking during tutor response interrupts and cycles back correctly

- [ ] **Step 4: Commit**

```bash
git add frontend/app.js
git commit -m "feat(speak-mode): integrate SpeakMode with setVoiceBarState transitions"
```

---

### Task 7: Handle Tab Visibility and Edge Cases

**Files:**
- Modify: `frontend/app.js` (add to SpeakMode module)

- [ ] **Step 1: Add tab visibility handler**

Add this inside the SpeakMode IIFE, before the `return` statement:

```javascript
  // Mute mic when tab loses focus to avoid background noise triggering interrupts
  document.addEventListener('visibilitychange', function() {
    if (!_active) return;
    if (document.hidden) {
      // Mute: stop sending audio but keep WS open
      if (_scriptNode) { try { _scriptNode.disconnect(); } catch(e) {} }
      console.log('[SpeakMode] Tab hidden — mic muted');
    } else {
      // Unmute: reconnect script node
      if (_audioCtx && _micStream && _scriptNode) {
        try {
          var source = _audioCtx.createMediaStreamSource(_micStream);
          source.connect(_analyser);
          source.connect(_scriptNode);
          _scriptNode.connect(_audioCtx.destination);
        } catch(e) { console.warn('[SpeakMode] Unmute error:', e); }
      }
      console.log('[SpeakMode] Tab visible — mic unmuted');
    }
  });
```

- [ ] **Step 2: Handle getUserMedia not available**

Add a check at the top of `enter()` to hide the mic toggle on unsupported browsers. Add this function inside the SpeakMode IIFE:

```javascript
  function checkSupport() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      var micToggle = document.getElementById('voice-bar-mic-toggle');
      if (micToggle) micToggle.style.display = 'none';
      return false;
    }
    return true;
  }
```

And add to the return object:

```javascript
    checkSupport: checkSupport,
```

- [ ] **Step 3: Call `checkSupport` on page load**

Find the `DOMContentLoaded` or equivalent initialization section in app.js. Add after the WebSocket initialization (`setTimeout(() => { if (_ws.enabled) wsConnect(); }, 1000);`):

```javascript
    // Hide speak mode button if browser doesn't support it
    if (typeof SpeakMode !== 'undefined') SpeakMode.checkSupport();
```

- [ ] **Step 4: Ensure `stopAll()` doesn't kill SpeakMode mic**

Verify in `stopAll()` (line 19250) that it does NOT close the SpeakMode AudioContext or mic stream. The existing `stopAll()` closes `state.voiceAudioCtx` (the TTS playback context) and kills `<audio>` elements, but SpeakMode uses its own `_audioCtx` and `_micStream` — these are internal to the IIFE and not referenced by `stopAll()`. Confirm this by reading the code. No changes needed if they're separate (they should be).

- [ ] **Step 5: Verify edge cases**

Test the following:
1. Switch to another browser tab while in speak mode, then switch back. Mic should resume.
2. Interrupt the tutor multiple times rapidly. System should remain stable.
3. On a browser without `getUserMedia` (or deny permission), the mic toggle button should be hidden or clicking it shows a toast.

- [ ] **Step 6: Commit**

```bash
git add frontend/app.js
git commit -m "feat(speak-mode): handle tab visibility, browser compat, and edge cases"
```

---

### Task 8: Final Polish and Integration Testing

**Files:**
- Modify: `frontend/app.js` (minor adjustments)
- Modify: `frontend/styles.css` (transition polish)

- [ ] **Step 1: Add smooth CSS transition between type and speak mode**

Add to `frontend/styles.css`:

```css
/* Smooth transition when toggling modes */
.voice-bar-wrap #voice-bar-main {
  transition: opacity 0.2s ease;
}
.voice-bar-wrap.speak-active #voice-bar-main {
  opacity: 0;
  pointer-events: none;
  position: absolute; /* collapse space */
}
.speak-mode-overlay {
  animation: speak-mode-enter 0.3s ease;
}
@keyframes speak-mode-enter {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}
```

- [ ] **Step 2: Disable CSS waveform animation when AnalyserNode is driving bars**

When the `_animateWaveform` rAF loop is running, the JS sets bar heights directly. The CSS `speak-wave` animation would conflict. Add this logic: when entering speak mode with mic active, add a class to disable CSS animation fallback.

In `_startAudioCapture`, after starting the animation loop, add:

```javascript
    // Disable CSS fallback animation — JS drives the bars now
    var waveformEl = document.getElementById('speak-waveform');
    if (waveformEl) waveformEl.classList.add('js-driven');
```

In `_stopAudioCapture`, add:

```javascript
    var waveformEl = document.getElementById('speak-waveform');
    if (waveformEl) waveformEl.classList.remove('js-driven');
```

Add this CSS rule:

```css
/* When JS drives the waveform, disable CSS animation */
.speak-waveform.js-driven span {
  animation: none !important;
}
```

- [ ] **Step 3: Full integration test**

Run through the complete flow:
1. Load app, verify type mode is default with mic toggle visible
2. Click mic toggle — speak mode enters with amber orb
3. Speak — orb goes green, waveform reacts to voice, transcription appears
4. Stop speaking — VAD auto-submits, orb goes amber with "Thinking..."
5. Tutor responds — orb goes purple with "Speak to interrupt..."
6. Speak during tutor response — tutor interrupted, new response starts
7. Click "Type" button — returns to textarea
8. Click mic toggle again — re-enters speak mode
9. Verify no console errors throughout

- [ ] **Step 4: Commit**

```bash
git add frontend/app.js frontend/styles.css
git commit -m "feat(speak-mode): polish transitions and disable CSS animation during JS-driven waveform"
```
