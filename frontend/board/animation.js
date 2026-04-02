/**
 * Animation — p5.js integration for inline board animations.
 * Creates p5 instances inside the DOM flow (not overlay layer).
 * Includes error recovery, blank detection, and Haiku auto-fix.
 */

import { board, registerElement } from './state.js';
import { createElement } from './renderer.js';
import { placeElement } from './placement.js';

/**
 * Sanitize LLM-generated animation code.
 * Fixes Unicode chars, smart quotes, and common issues.
 * @param {string} code
 * @returns {string}
 */
function sanitizeCode(code) {
  code = code.replace(/[\u2018\u2019\u201A\u2032]/g, "'");
  code = code.replace(/[\u201C\u201D\u201E\u2033]/g, '"');
  code = code.replace(/[\u2013\u2014\u2212]/g, '-');
  code = code.replace(/[\u200B\u200C\u200D\uFEFF]/g, '');
  code = code.replace(/\u00D7/g, '*');
  code = code.replace(/\u00F7/g, '/');
  code = code.replace(/\u2264/g, '<=');
  code = code.replace(/\u2265/g, '>=');
  code = code.replace(/\u2260/g, '!=');
  code = code.replace(/\u03C0/g, 'Math.PI');
  code = code.replace(/\u00A0/g, ' ');
  code = code.replace(/^```(?:javascript|js)?\s*/i, '').replace(/\s*```\s*$/, '');

  // Balance brackets
  const stack = [];
  let inStr = false, esc = false;
  for (let i = 0; i < code.length; i++) {
    const ch = code[i];
    if (esc) { esc = false; continue; }
    if (ch === '\\') { esc = true; continue; }
    if (ch === "'" || ch === '"' || ch === '`') { inStr = !inStr; continue; }
    if (inStr) continue;
    if (ch === '{') stack.push('}');
    else if (ch === '(') stack.push(')');
    else if (ch === '[') stack.push(']');
    else if (ch === '}' || ch === ')' || ch === ']') stack.pop();
  }
  if (stack.length) code += stack.reverse().join('');

  // Strip re-declarations of W, H, S
  code = code.replace(/\b(let|const|var)\s+(W|H)\b\s*=/g, '$2 =');
  code = code.replace(/\b(let|const|var)\s+S\b\s*=/g, 'S =');

  return code;
}

/**
 * Build the control bridge code that's injected before the animation.
 * @param {number} scale - Animation scale factor
 * @param {boolean} isWebGL - Whether this is a WEBGL animation
 * @returns {string}
 */
function buildControlBridge(scale, isWebGL) {
  return `
    var _controlParams = {};
    var S = ${scale.toFixed(2)};
    function onControl(params) {
      if (params._unhighlight) { _controlParams._highlight = null; }
      Object.assign(_controlParams, params);
      // Forward to AnimHelper if available
      if (p._animHelper && p._animHelper._onControl) { p._animHelper._onControl(params); }
    }
    p._onControl = function(params) { onControl(params); };
    function sTextSize(sz) { return sz * S; }
    function sStroke(w) { return Math.max(1, w * S); }
    function applyHighlight(p, color, isHighlighted) {
      if (isHighlighted) { p.strokeWeight(sStroke(3)); p.drawingContext.shadowColor = color || '#34d399'; p.drawingContext.shadowBlur = 18 * S; }
      else { p.strokeWeight(sStroke(1.5)); p.drawingContext.shadowBlur = 0; }
    }
    // Proxy Canvas2D methods LLMs call on p instead of p.drawingContext
    ['setLineDash','getLineDash','setTransform','resetTransform','clip','clearRect',
     'createLinearGradient','createRadialGradient','measureText','fillRect','strokeRect'].forEach(function(m) {
      if (!p[m] && p.drawingContext && typeof p.drawingContext[m] === 'function') {
        p[m] = function() { return p.drawingContext[m].apply(p.drawingContext, arguments); };
      }
    });
    ${isWebGL ? `
    p.text = function() {};
    p.textFont = function() {};
    p.textSize = function() {};
    p.textAlign = function() {};
    ` : ''}
  `;
}

/**
 * Create a p5.js animation element inline in the board flow.
 * @param {Object} cmd - Animation command with `code` field
 */
export async function createAnimation(cmd) {
  if (!cmd.code) return;

  const el = createElement('div', cmd, 'bd-anim-box');

  // Expand button
  const controls = document.createElement('div');
  controls.className = 'bd-anim-controls';
  const expandBtn = document.createElement('button');
  expandBtn.className = 'bd-anim-expand-btn';
  expandBtn.textContent = '⛶';
  expandBtn.title = 'Expand animation';
  expandBtn.addEventListener('click', () => {
    // TODO: fullscreen modal
  });
  controls.appendChild(expandBtn);
  el.appendChild(controls);

  // Canvas wrapper
  const canvasWrap = document.createElement('div');
  canvasWrap.className = 'bd-anim-canvas-wrap';
  el.appendChild(canvasWrap);

  // Place in DOM flow BEFORE creating p5 instance
  placeElement(el, cmd.placement, cmd);

  // Determine dimensions from actual DOM size (not estimated!)
  const elRect = el.getBoundingClientRect();
  const pw = Math.round(elRect.width) || 300;
  const ph = Math.round(elRect.height) || 200;

  // Build and compile code
  const isWebGL = /p\.WEBGL|,\s*WEBGL/.test(cmd.code);
  const scale = pw / 300;
  let code = sanitizeCode(cmd.code);
  code = code.replace(/p\.textSize\((\d+(?:\.\d+)?)\)/g, (_, n) => `p.textSize(${n} * S)`);
  code = code.replace(/p\.strokeWeight\((\d+(?:\.\d+)?)\)/g, (_, n) => `p.strokeWeight(Math.max(1, ${n} * S))`);
  const fullCode = buildControlBridge(scale, isWebGL) + '\n' + code;

  let sketchFn;
  try {
    sketchFn = new Function('p', 'W', 'H', fullCode);
  } catch (e) {
    // Try stripping non-ASCII
    try {
      sketchFn = new Function('p', 'W', 'H', fullCode.replace(/[^\x00-\x7F]/g, ''));
    } catch (e2) {
      console.warn('[Animation] Compile error — calling syntax fix:', e.message);
      showSkeleton(el, canvasWrap, cmd, e.message, scale, isWebGL);
      return;
    }
  }

  // Create p5 instance
  let inst;
  try {
    inst = new p5(p => {
      try { sketchFn(p, pw, ph); } catch (err) {
        console.error('[Animation] Sketch error:', err.message);
        canvasWrap.innerHTML = '<div style="padding:12px;color:rgba(248,113,113,0.4);font-size:12px;font-family:monospace">Animation error</div>';
        return;
      }
      // Wrap draw() in error boundary
      const userDraw = p.draw;
      if (userDraw) {
        let errors = 0;
        p.draw = function () {
          try { userDraw.call(p); } catch (err) {
            if (++errors === 1) console.log('[Animation] draw() has a minor error (animation still runs):', err.message);
            if (errors >= 30) p.noLoop();
          }
        };
      }
      const userSetup = p.setup;
      p.setup = function () {
        if (userSetup) userSetup.call(p);
        try { if (!p._renderer.isP3D) p.textFont('sans-serif'); } catch (e) {}
        // Auto-inject AnimHelper if LLM didn't create one
        if (!p._animHelper && typeof AnimHelper !== 'undefined' && !p._renderer?.isP3D) {
          try {
            const _a = new AnimHelper(p, p.width, p.height);
            p._animHelper = _a;
            console.log('[Animation] AnimHelper auto-injected');
          } catch (e) { console.warn('[Animation] AnimHelper auto-inject failed:', e); }
        }
      };
      // Note: anim-control forwarding to AnimHelper is handled by buildControlBridge's onControl()
    }, canvasWrap);
  } catch (e) {
    canvasWrap.innerHTML = '<div style="padding:12px;color:rgba(248,113,113,0.4);font-size:12px">Init error</div>';
    return;
  }

  el._p5Instance = inst;
  const entry = { container: el, instance: inst, _running: true };
  board.animations.push(entry);

  // Blank detection disabled — Haiku fix causes more harm than good
  // const retryKey = cmd.id || 'anon';
  // const attempt = board.animRetries.get(retryKey) || 0;
  // if (attempt < 1) {
  //   setTimeout(() => detectBlank(canvasWrap, entry, cmd, retryKey, attempt), 2500);
  // }
}

/**
 * Check if animation canvas is blank and trigger Haiku fix.
 */
function detectBlank(canvasWrap, entry, cmd, retryKey, attempt) {
  try {
    const cvs = canvasWrap.querySelector('canvas');
    if (!cvs || cvs.width === 0) return;
    const ctx = cvs.getContext('2d', { willReadFrequently: true });
    if (!ctx) return;
    const data = ctx.getImageData(0, 0, cvs.width, cvs.height).data;
    const step = Math.max(4, Math.floor(data.length / 200)) & ~3;
    let bright = 0;
    for (let i = 0; i < data.length; i += step) {
      if (data[i] > 25 || data[i + 1] > 30 || data[i + 2] > 25) bright++;
    }
    if (bright >= 3) return; // has content

    board.animRetries.set(retryKey, attempt + 1);
    console.warn('[Animation] Blank detected — calling Haiku fix:', retryKey);

    fetch(`${board.apiUrl}/api/fix-animation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: cmd.code, error: 'Canvas all black. Fix drawing logic.' }),
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data?.code) throw new Error('No code');
        try { entry.instance.remove(); } catch (e) {}
        if (entry.container?.parentNode) entry.container.parentNode.removeChild(entry.container);
        const idx = board.animations.indexOf(entry);
        if (idx >= 0) board.animations.splice(idx, 1);
        createAnimation({ ...cmd, code: data.code });
      })
      .catch(() => {
        // Give up — remove animation container entirely
        try { entry.instance.remove(); } catch (e) {}
        if (entry.container?.parentNode) entry.container.parentNode.removeChild(entry.container);
        const idx = board.animations.indexOf(entry);
        if (idx >= 0) board.animations.splice(idx, 1);
      });
  } catch (e) {}
}

/**
 * Show skeleton loading state and call Haiku to fix broken code.
 */
function showSkeleton(el, canvasWrap, cmd, errorMsg, scale, isWebGL) {
  canvasWrap.innerHTML = `
    <div style="width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;min-height:150px">
      <div style="width:36px;height:36px;border:2px solid rgba(52,211,153,0.3);border-top-color:rgba(52,211,153,0.8);border-radius:50%;animation:spin 1s linear infinite"></div>
      <div style="color:rgba(52,211,153,0.5);font-size:12px;font-family:monospace">fixing animation...</div>
    </div>
    <style>@keyframes spin{to{transform:rotate(360deg)}}</style>
  `;

  fetch(`${board.apiUrl}/api/fix-animation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code: cmd.code, error: errorMsg }),
  })
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if (!data?.code) throw new Error('No code');
      // Replace skeleton with fixed animation
      canvasWrap.innerHTML = '';
      const fixedCode = sanitizeCode(data.code);
      const fullCode = buildControlBridge(scale, isWebGL) + '\n' + fixedCode;
      const fn = new Function('p', 'W', 'H', fullCode);
      const rect = el.getBoundingClientRect();
      const inst = new p5(p => {
        try { fn(p, Math.round(rect.width) || 300, Math.round(rect.height) || 200); } catch (e) {
          canvasWrap.innerHTML = '<div style="padding:12px;color:rgba(255,255,255,0.2);font-size:12px">Animation unavailable</div>';
          return;
        }
        const userSetup = p.setup;
        p.setup = function () {
          if (userSetup) userSetup.call(p);
          try { if (!p._renderer.isP3D) p.textFont('sans-serif'); } catch (e) {}
          if (!p._animHelper && typeof AnimHelper !== 'undefined' && !p._renderer?.isP3D) {
            try { p._animHelper = new AnimHelper(p, p.width, p.height); } catch (e) {}
          }
        };
      }, canvasWrap);
      el._p5Instance = inst;
      board.animations.push({ container: el, instance: inst, _running: true });
    })
    .catch(() => {
      // Remove the animation element entirely
      if (el.parentNode) el.parentNode.removeChild(el);
    });
}
