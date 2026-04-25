# Inline Mic Input Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two-mode (Type/Speak) voice bar with a single unified input where the mic button temporarily activates inline listening with waveform overlay, VAD auto-sends, and returns to typing.

**Architecture:** Remove the entire SpeakMode IIFE and speak-mode HTML/CSS. Keep the mic button in the bottom row but change its onclick to a new lightweight `InlineMic` module. When tapped, an absolute-positioned waveform overlay appears over the textarea. Audio pipeline and Scribe WS logic are extracted from the old SpeakMode into InlineMic.

**Tech Stack:** Web Audio API (getUserMedia, AudioContext@16kHz, AnalyserNode, ScriptProcessorNode), ElevenLabs Scribe v2 via `/ws/scribe` WebSocket relay, vanilla JS IIFE.

**Spec:** `docs/superpowers/specs/2026-04-25-inline-mic-input.md`

---

### Task 1: Remove Old Speak Mode HTML and CSS

**Files:**
- Modify: `frontend/index.html:1224-1259` — remove `#vb-speak-content` div and all children
- Modify: `frontend/styles.css:7736-7930` — remove all `.vb-speak-content`, `.speak-orb-*`, `.speak-waveform`, `.speak-transcript`, `.speak-bottom`, `.speak-keyboard-btn`, `.speak-mic-active` CSS

- [ ] **Step 1: Remove the `#vb-speak-content` div from HTML**

In `frontend/index.html`, delete lines 1224–1259 (the `<!-- Speak mode content -->` comment through the closing `</div>` of `vb-speak-content`). The `#vb-type-content` div and `#voice-bar-main` closing tag remain.

After removal, lines around 1223 should look like:

```html
          </div>
          <!-- /vb-type-content -->
        </div>
      </div>
```

- [ ] **Step 2: Remove old speak mode CSS**

In `frontend/styles.css`, delete everything from the comment `/* Speak mode content — lives inside .voice-bar */` (line 7736) through the end of the `.speak-bottom-right` / `.speak-mic-active` rules (approximately line 7930+). This removes:
- `.vb-speak-content` and `.vb-speak-content.hidden`
- `.speak-orb-container`, `.speak-orb`, `.speak-orb-glow`, `.speak-orb-inner`
- All orb color state selectors (`.vb-speak-content.speak-idle`, `.speak-listening`, `.speak-tutor`)
- `@keyframes speak-tutor-aura`
- `.speak-waveform` and all waveform span animation rules
- `@keyframes speak-idle-pulse`, `@keyframes speak-tutor-pulse`
- `.speak-waveform.js-driven`
- `.speak-transcript`
- `.speak-bottom`, `.speak-bottom-left`, `.speak-bottom-right`
- `.speak-keyboard-btn`, `.speak-mic-active`

Keep the `.vb-mic-toggle` styles (lines 7718-7734) — the mic button stays.

- [ ] **Step 3: Add waveform overlay CSS**

Append to `frontend/styles.css` after the `.vb-mic-toggle:hover` rule:

```css
/* ── Inline mic waveform overlay ── */
.vb-waveform-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 16px;
  background: rgba(12,16,22,0.92);
  border-radius: 14px;
  z-index: 2;
  pointer-events: none;
}
.vb-waveform-overlay.hidden { display: none; }

.vb-waveform-overlay .inline-waveform {
  display: flex;
  align-items: center;
  gap: 2px;
  height: 24px;
}
.vb-waveform-overlay .inline-waveform span {
  display: block;
  width: 2.5px;
  height: 6px;
  border-radius: 1.5px;
  background: #34d399;
  transition: height .08s ease;
}
.vb-waveform-overlay .listening-label {
  font-size: 13px;
  color: rgba(255,255,255,.5);
  white-space: nowrap;
}

/* Mic button listening state */
.vb-mic-toggle.listening {
  color: #34d399;
  border-color: rgba(52,211,153,.4);
  background: rgba(52,211,153,.12);
}
```

- [ ] **Step 4: Add waveform overlay HTML**

In `frontend/index.html`, inside `#vb-type-content` just before the `<textarea>`, add:

```html
            <div class="vb-waveform-overlay hidden" id="vb-waveform-overlay">
              <div class="inline-waveform" id="inline-waveform">
                <span></span><span></span><span></span><span></span><span></span><span></span><span></span>
              </div>
              <span class="listening-label">Listening...</span>
            </div>
```

Also add `position: relative` to `#vb-type-content` so the overlay positions correctly. In `styles.css`:

```css
.vb-type-content {
  position: relative;
}
```

- [ ] **Step 5: Verify and commit**

Open in browser. Voice bar should look identical to before (textarea + bottom controls + mic button). No speak mode orb/overlay. Waveform overlay div is present but hidden.

```bash
git add frontend/index.html frontend/styles.css
git commit -m "refactor: remove old speak mode HTML/CSS, add inline waveform overlay structure"
```

---

### Task 2: Remove Old SpeakMode JS and state.inputMode

**Files:**
- Modify: `frontend/app.js:810-811` — remove `inputMode` from state
- Modify: `frontend/app.js:1343-1752` — remove entire `SpeakMode` IIFE and `window.SpeakMode` assignment
- Modify: `frontend/app.js:19817-19852` — remove speak mode branch in `setVoiceBarState`
- Modify: `frontend/app.js:19854` — remove `if (state.inputMode !== 'speak')` guard (make the type-mode switch always run)
- Modify: `frontend/app.js:20164` — remove `.speak-orb-container`, `.speak-mic-active`, `.speak-keyboard-btn` from drag handler exclusion
- Modify: `frontend/app.js:18058` — remove `SpeakMode.checkSupport()` call
- Modify: `frontend/index.html:1218` — change mic button onclick from `SpeakMode.toggle()` to `InlineMic.toggle()`

- [ ] **Step 1: Remove `inputMode` from state object**

In `frontend/app.js`, delete lines 810-811:

```js
  // Input mode: 'type' (default textarea) or 'speak' (tap-to-talk)
  inputMode: 'type',
```

- [ ] **Step 2: Remove entire SpeakMode IIFE**

Delete lines 1343-1752 (from `var SpeakMode = (() => {` through `window.SpeakMode = SpeakMode;` and the blank lines after).

- [ ] **Step 3: Remove speak mode branch in setVoiceBarState**

In `setVoiceBarState`, delete lines 19816-19852 (the `// ── Speak mode overlay state ──` comment through the closing `}` of the speak mode block).

Then change line 19854 from:

```js
  if (state.inputMode !== 'speak') {
```

to just remove the `if` wrapper entirely — the type-mode switch block should always run. Also remove the corresponding closing `} // end if (state.inputMode !== 'speak')` at line 19907.

- [ ] **Step 4: Clean up drag handler exclusions**

In the drag handler at line 20164, change:

```js
    if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'BUTTON' || e.target.tagName === 'INPUT' || e.target.closest('button') || e.target.closest('.speak-orb-container') || e.target.closest('.speak-mic-active') || e.target.closest('.speak-keyboard-btn')) return;
```

to:

```js
    if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'BUTTON' || e.target.tagName === 'INPUT' || e.target.closest('button')) return;
```

- [ ] **Step 5: Remove SpeakMode.checkSupport() call**

At line 18058, delete:

```js
    if (typeof SpeakMode !== 'undefined') SpeakMode.checkSupport();
```

- [ ] **Step 6: Update mic button onclick in HTML**

In `frontend/index.html`, change the mic button from:

```html
<button class="vb-mic-toggle" id="voice-bar-mic-toggle" onclick="SpeakMode.toggle()" title="Switch to speak mode">
```

to:

```html
<button class="vb-mic-toggle" id="voice-bar-mic-toggle" onclick="InlineMic.toggle()" title="Voice input">
```

- [ ] **Step 7: Verify and commit**

Open in browser. Voice bar should work for typing. Mic button should be visible but clicking it will log an error (InlineMic not defined yet). No JS errors on page load.

```bash
git add frontend/app.js frontend/index.html
git commit -m "refactor: remove SpeakMode IIFE, inputMode state, speak mode setVoiceBarState branch"
```

---

### Task 3: Implement InlineMic Module

**Files:**
- Modify: `frontend/app.js` — add `InlineMic` IIFE after the old SpeakMode location (around line 1343)

This module reuses the audio pipeline and Scribe WS logic from the old SpeakMode but is much simpler — no enter/exit modes, no orb, no transcript. Just: toggle listening on/off, show/hide waveform overlay, auto-submit on VAD commit.

- [ ] **Step 1: Add InlineMic IIFE**

Insert at the location where SpeakMode was removed (around line 1343, before Module 5):

```js
// ═══════════════════════════════════════════════════════════
// Module 4b: Inline Mic Input
// ═══════════════════════════════════════════════════════════

var InlineMic = (() => {
  var _listening = false;
  var _scribeWs = null;
  var _micStream = null;
  var _audioCtx = null;
  var _analyser = null;
  var _scriptNode = null;
  var _animFrameId = null;
  var _committed = '';
  var _submitTimer = null;
  var _tapDebounce = 0;

  function isListening() { return _listening; }

  function toggle() {
    if (_listening) {
      // Stop = dismiss, don't send
      _stopAndDiscard();
    } else {
      _startListening();
    }
  }

  async function _startListening() {
    // Debounce rapid taps (300ms)
    var now = Date.now();
    if (now - _tapDebounce < 300) return;
    _tapDebounce = now;

    // If tutor is speaking, stop it first
    if (state.isStreaming) {
      stopAll();
    }

    // Acquire mic
    if (!_micStream) {
      try {
        _micStream = await navigator.mediaDevices.getUserMedia({
          audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true }
        });
      } catch (err) {
        console.warn('[InlineMic] Mic permission denied:', err);
        _showToast('Microphone access required');
        return;
      }
    }

    _listening = true;
    _committed = '';
    if (_submitTimer) { clearTimeout(_submitTimer); _submitTimer = null; }

    // Show waveform overlay
    var overlay = document.getElementById('vb-waveform-overlay');
    if (overlay) overlay.classList.remove('hidden');

    // Swap mic icon to stop icon
    var micBtn = document.getElementById('voice-bar-mic-toggle');
    if (micBtn) {
      micBtn.classList.add('listening');
      micBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>';
      micBtn.title = 'Cancel voice input';
    }

    // Start audio capture + Scribe WS
    _startAudioCapture(_micStream);
    _connectScribe();

    console.log('[InlineMic] Started listening');
  }

  function _stopListening() {
    if (!_listening) return;
    _listening = false;

    // Stop audio processing
    _stopAudioCapture();

    // Close Scribe WS
    _disconnectScribe();

    // Clear pending submit
    if (_submitTimer) { clearTimeout(_submitTimer); _submitTimer = null; }

    // Hide waveform overlay
    var overlay = document.getElementById('vb-waveform-overlay');
    if (overlay) overlay.classList.add('hidden');

    // Restore mic icon
    var micBtn = document.getElementById('voice-bar-mic-toggle');
    if (micBtn) {
      micBtn.classList.remove('listening');
      micBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="9" y="2" width="6" height="11" rx="3"/><path d="M5 10a7 7 0 0014 0"/><line x1="12" y1="19" x2="12" y2="22"/></svg>';
      micBtn.title = 'Voice input';
    }

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

    console.log('[InlineMic] Stopped listening');
  }

  function _stopAndDiscard() {
    _committed = '';
    _stopListening();
    console.log('[InlineMic] Dismissed — nothing sent');
  }

  function _autoSubmit() {
    var spokenText = _committed.trim();
    _committed = '';
    _submitTimer = null;

    _stopListening();

    if (!spokenText) return;

    // Append spoken text to any existing typed text
    var field = document.getElementById('voice-bar-input');
    if (field) {
      var existing = field.value.trim();
      field.value = existing ? existing + ' ' + spokenText : spokenText;
    }

    // Submit
    console.log('[InlineMic] Auto-submit: "' + spokenText.slice(0, 40) + '"');
    submitVoiceBarInput();
  }

  // ── Audio Capture ──

  function _startAudioCapture(stream) {
    if (!_audioCtx) {
      _audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
    }
    var source = _audioCtx.createMediaStreamSource(stream);

    _analyser = _audioCtx.createAnalyser();
    _analyser.fftSize = 256;
    _analyser.smoothingTimeConstant = 0.7;
    source.connect(_analyser);

    _scriptNode = _audioCtx.createScriptProcessor(4096, 1, 1);
    _scriptNode.onaudioprocess = function(e) {
      if (!_listening || !_scribeWs || _scribeWs.readyState !== WebSocket.OPEN) return;
      var input = e.inputBuffer.getChannelData(0);
      var pcm16 = new Int16Array(input.length);
      for (var i = 0; i < input.length; i++) {
        var s = Math.max(-1, Math.min(1, input[i]));
        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      var bytes = new Uint8Array(pcm16.buffer);
      var binary = '';
      for (var j = 0; j < bytes.length; j++) binary += String.fromCharCode(bytes[j]);
      var b64 = btoa(binary);
      try {
        _scribeWs.send(JSON.stringify({ type: 'audio', data: b64 }));
      } catch (err) {
        console.warn('[InlineMic] Audio send error:', err);
      }
    };

    _analyser.connect(_scriptNode);
    _scriptNode.connect(_audioCtx.destination);

    // Start waveform animation
    _animateWaveform();
  }

  function _stopAudioCapture() {
    if (_animFrameId) { cancelAnimationFrame(_animFrameId); _animFrameId = null; }
    if (_scriptNode) {
      try { _scriptNode.disconnect(); } catch (e) {}
      _scriptNode = null;
    }
    if (_analyser) {
      try { _analyser.disconnect(); } catch (e) {}
      _analyser = null;
    }
    _resetWaveformBars();
  }

  // ── Waveform Animation ──

  function _animateWaveform() {
    if (!_analyser || !_listening) return;
    var bars = document.querySelectorAll('#inline-waveform span');
    if (!bars.length) return;

    var dataArray = new Uint8Array(_analyser.frequencyBinCount);

    function draw() {
      if (!_listening || !_analyser) return;
      _animFrameId = requestAnimationFrame(draw);
      _analyser.getByteFrequencyData(dataArray);

      var step = Math.floor(dataArray.length / bars.length);
      for (var i = 0; i < bars.length; i++) {
        var val = dataArray[i * step] || 0;
        var h = Math.max(4, (val / 255) * 20);
        bars[i].style.height = h + 'px';
      }
    }
    draw();
  }

  function _resetWaveformBars() {
    var bars = document.querySelectorAll('#inline-waveform span');
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
      console.log('[InlineMic] Scribe WS opened');
    };

    _scribeWs.onmessage = function(e) {
      var msg;
      try { msg = JSON.parse(e.data); } catch (err) { return; }

      if (msg.type === 'ready') {
        console.log('[InlineMic] Scribe ready');
        return;
      }

      if (msg.type === 'committed') {
        var text = msg.text || '';
        if (text.trim()) {
          _committed += (_committed ? ' ' : '') + text.trim();
        }

        // Debounce: wait 500ms after last committed before auto-submitting
        if (_submitTimer) clearTimeout(_submitTimer);
        _submitTimer = setTimeout(function() {
          _autoSubmit();
        }, 500);
        return;
      }

      if (msg.type === 'partial') {
        // Ignored per spec — we just show "Listening..." not live text
        // But still interrupt tutor if speaking and partial is substantial
        var partial = msg.text || '';
        if (state.isStreaming && partial.length > 5) {
          stopAll();
        }
        return;
      }

      if (msg.type === 'error') {
        console.warn('[InlineMic] Scribe error:', msg.message);
        _showToast(msg.message || 'Voice error');
        _stopAndDiscard();
        return;
      }
    };

    _scribeWs.onclose = function() {
      console.log('[InlineMic] Scribe WS closed');
      _scribeWs = null;
    };

    _scribeWs.onerror = function(err) {
      console.warn('[InlineMic] Scribe WS error:', err);
      _scribeWs = null;
      if (_listening) {
        _showToast('Voice connection error');
        _stopAndDiscard();
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

  function _showToast(msg) {
    if (typeof showToast === 'function') showToast(msg);
    else console.warn('[InlineMic]', msg);
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
      console.log('[InlineMic] Tab hidden — stopping');
      _stopAndDiscard();
    }
  });

  return {
    isListening: isListening,
    toggle: toggle,
    checkSupport: checkSupport,
  };
})();
window.InlineMic = InlineMic;
```

- [ ] **Step 2: Add InlineMic.checkSupport() call**

Find the location where `SpeakMode.checkSupport()` was removed (around the session initialization) and add:

```js
    if (typeof InlineMic !== 'undefined') InlineMic.checkSupport();
```

- [ ] **Step 3: Verify and commit**

Open in browser. Tap mic button → waveform overlay appears on textarea, mic icon becomes stop square. Speak → VAD commits → text appears in textarea → auto-submits. Tap stop → dismissed, nothing sent. Typed text preserved when appending.

```bash
git add frontend/app.js
git commit -m "feat: add InlineMic module — inline voice input with waveform overlay and VAD auto-submit"
```

---

### Task 4: Handle Edge Cases

**Files:**
- Modify: `frontend/app.js` — adjust `submitVoiceBarInput` and `setVoiceBarState` for inline mic interactions

- [ ] **Step 1: Stop listening when send button is tapped manually**

In `submitVoiceBarInput` (around line 19997), add at the top of the function:

```js
  // If mic is listening, stop it and discard spoken text — submit typed text only
  if (typeof InlineMic !== 'undefined' && InlineMic.isListening()) {
    InlineMic.toggle(); // stops and discards
  }
```

- [ ] **Step 2: Stop listening when tutor state changes to thinking**

In `setVoiceBarState`, inside the `case 'thinking':` block, add:

```js
      // Stop inline mic if listening (tutor is about to respond)
      if (typeof InlineMic !== 'undefined' && InlineMic.isListening()) {
        // Don't stop — let it finish naturally or let user stop manually
      }
```

(No action needed — the mic should keep listening while tutor thinks if user started speaking before response came. The VAD will commit naturally.)

- [ ] **Step 3: Verify edge cases and commit**

Test the following:
1. Type some text → tap mic → speak → VAD commits → typed + spoken text both sent
2. Tap mic → speak → tap stop → nothing sent, textarea empty
3. Type some text → tap mic → tap stop → typed text remains in textarea
4. Tap mic → speak → while listening, response comes back → mic still works
5. Double-tap mic rapidly → only one action fires
6. Deny mic permission → toast shows, stays in type mode

```bash
git add frontend/app.js
git commit -m "feat: handle inline mic edge cases — send button stops mic, typed text preservation"
```

---

### Task 5: Clean Up Unused CSS and Final Polish

**Files:**
- Modify: `frontend/styles.css` — remove any remaining orphaned speak mode CSS
- Modify: `frontend/index.html` — clean up any remaining speak mode element IDs or comments

- [ ] **Step 1: Search for and remove orphaned references**

Search all frontend files for any remaining references to: `speak-mode`, `speak-orb`, `speak-transcript`, `speak-bottom`, `speak-keyboard`, `speak-mic-active`, `speak-idle`, `speak-listening`, `speak-tutor`, `speak-active`, `vb-speak-content`, `inputMode`. Remove any found.

- [ ] **Step 2: Verify clean state**

Run a grep to confirm no old speak mode references remain:

```bash
grep -rn "speak-mode\|speak-orb\|SpeakMode\|speak-active\|vb-speak-content\|inputMode" frontend/
```

Should return zero results.

- [ ] **Step 3: Verify full flow end-to-end**

1. Start a tutor session
2. Type a response → send → tutor responds (normal flow works)
3. Tap mic → waveform overlay appears → speak → VAD commits → auto-sends → tutor responds
4. Tap mic → speak → tap stop → dismissed, nothing sent
5. Type partial text → tap mic → speak → VAD commits → combined text sent
6. Mic button is hidden when getUserMedia is not supported

```bash
git add frontend/
git commit -m "chore: clean up remaining speak mode references"
```
