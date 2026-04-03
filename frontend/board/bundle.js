/**
 * Board Engine — bundled IIFE for non-module <script> inclusion.
 * Combines: state, renderer, text-animator, placement, commands,
 *           animation, scene, highlight, index.
 *
 * Exposes: window.BoardEngine
 *
 * AUTO-GENERATED from ES module sources — do not edit directly.
 */
(function () {
'use strict';

// ═══════════════════════════════════════════════════════════════
// 1. STATE
// ═══════════════════════════════════════════════════════════════

const board = {
  liveScene: null,
  currentRow: null,
  currentColumns: null,
  cancelFlag: false,
  pauseFlag: false,
  commandQueue: [],
  isProcessing: false,
  elements: new Map(),
  scenes: [],
  animations: [],
  zoom: 1,
  animRetries: new Map(),
  apiUrl: '',
};

function resetState() {
  board.liveScene = null;
  board.currentRow = null;
  board.currentColumns = null;
  board.cancelFlag = false;
  board.commandQueue = [];
  board.isProcessing = false;
  board.elements.clear();
  board.scenes = [];
  board.animations.forEach(a => { try { a.instance.remove(); } catch(e) {} });
  board.animations = [];
  board.zoom = 1.15;
  board.animRetries.clear();
}

function registerElement(id, element) {
  if (!id) return;
  board.elements.set(id, {
    element,
    scene: board.scenes.length,
  });
}

function getElement(id) {
  const entry = board.elements.get(id);
  if (!entry) return null;
  if (entry.scene !== board.scenes.length) return null;
  return entry.element;
}

function getElementAny(id) {
  return board.elements.get(id) || null;
}

function endRow() {
  board.currentRow = null;
}

// ═══════════════════════════════════════════════════════════════
// 2. RENDERER
// ═══════════════════════════════════════════════════════════════

const COLOR_MAP = {
  white: 'white', yellow: 'yellow', gold: 'gold', green: 'green',
  blue: 'cyan', red: 'red', cyan: 'cyan', dim: 'dim',
  '#e8e8e0': 'white', '#f5d97a': 'yellow', '#fbbf24': 'gold',
  '#34d399': 'green', '#7ed99a': 'green', '#53d8fb': 'cyan',
  '#ff6b6b': 'red', '#94a3b8': 'dim', '#e2e8f0': 'white',
  '#fb7185': 'red', '#a78bfa': 'cyan',
};

const SIZE_MAP = {
  h1: 'h1', h2: 'h2', h3: 'h3', text: 'text', body: 'text',
  small: 'small', label: 'label', caption: 'label',
};

function colorClass(color) {
  if (!color) return 'bd-chalk-white';
  var mapped = COLOR_MAP[color.toLowerCase ? color.toLowerCase() : color] || COLOR_MAP[color];
  return 'bd-chalk-' + (mapped || 'white');
}

function sizeClass(size) {
  if (!size) return 'bd-size-text';
  if (typeof size === 'string') {
    var mapped = SIZE_MAP[size.toLowerCase()];
    return 'bd-size-' + (mapped || 'text');
  }
  if (size >= 24) return 'bd-size-h1';
  if (size >= 19) return 'bd-size-h2';
  if (size >= 16) return 'bd-size-text';
  if (size >= 12) return 'bd-size-small';
  return 'bd-size-label';
}

function createElement(tag, cmd) {
  var extraClasses = Array.prototype.slice.call(arguments, 2);
  var el = document.createElement(tag);
  el.className = ['bd-el'].concat(extraClasses).filter(Boolean).join(' ');
  if (cmd.id) el.id = cmd.id;
  if (cmd.cmd) el.dataset.cmd = cmd.cmd;
  return el;
}

function createStyledElement(tag, cmd) {
  var extraClasses = Array.prototype.slice.call(arguments, 2);
  var el = createElement.apply(null, [tag, cmd, colorClass(cmd.color), sizeClass(cmd.size)].concat(extraClasses));
  return el;
}

// ═══════════════════════════════════════════════════════════════
// 3. TEXT ANIMATOR
// ═══════════════════════════════════════════════════════════════

function sleep(ms) {
  return new Promise(function(resolve) { setTimeout(resolve, ms); });
}

async function animateText(parentEl, text, options) {
  options = options || {};
  if (!text) return;

  var queueLen = board.commandQueue.length;
  var animCount = board.animations.length;
  var instant = options.instant || board.replayMode || queueLen > 5 || animCount > 4;
  var delay = options.charDelay;
  if (delay === undefined) {
    delay = animCount > 2 ? 15 : animCount > 0 ? 25 : 35;
  }

  // Convert \n to line breaks for multi-line text
  var hasNewlines = text.indexOf('\n') >= 0;
  function escapeAndBreak(t) {
    return t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');
  }

  if (instant || delay === 0) {
    if (hasNewlines) {
      parentEl.innerHTML = escapeAndBreak(text);
    } else {
      parentEl.textContent = text;
    }
    return;
  }

  var fragment = document.createDocumentFragment();
  var chars = [];
  for (var ch of text) {
    if (ch === '\n') {
      var br = document.createElement('br');
      br.classList.add('bd-char-visible');
      fragment.appendChild(br);
      continue;
    }
    var span = document.createElement('span');
    span.className = 'bd-char';
    span.textContent = ch;
    chars.push(span);
    fragment.appendChild(span);
  }
  parentEl.appendChild(fragment);

  for (var span of chars) {
    if (board.cancelFlag) {
      chars.forEach(function(s) { s.classList.add('bd-char-visible'); });
      break;
    }
    span.classList.add('bd-char-visible');
    await sleep(delay);
  }

  if (hasNewlines) {
    parentEl.innerHTML = escapeAndBreak(text);
  } else {
    parentEl.textContent = text;
  }
}

// ═══════════════════════════════════════════════════════════════
// 4. PLACEMENT
// ═══════════════════════════════════════════════════════════════

function endCurrentRowIfNeeded(placement) {
  if (placement !== 'row-start' && placement !== 'row-next') {
    endRow();
  }
}

function placeElement(element, placement, cmd) {
  var scene = board.liveScene;
  if (!scene) return;

  placement = placement || 'below';

  if (cmd.id) {
    registerElement(cmd.id, element);
  }

  // ── PERCENTAGE-BASED ABSOLUTE POSITIONING ──
  // If cmd has x/y (0-100), position absolutely within the scene.
  // This gives the LLM free spatial control like a real chalkboard.
  if (typeof cmd.x === 'number' && typeof cmd.y === 'number') {
    // ── Fixed drawing canvas: all positioned elements live in a constrained area ──
    // The canvas is a fixed-aspect-ratio box (800x500 logical units) inside the scene.
    // x,y are 0-100 percentages of this canvas, NOT the scene.
    var canvas = scene.querySelector('.bd-draw-canvas');
    if (!canvas) {
      canvas = document.createElement('div');
      canvas.className = 'bd-draw-canvas';
      // Fixed aspect ratio container — all positioned content goes here
      canvas.style.cssText = 'position:relative;width:100%;max-width:800px;margin:8px auto;' +
        'aspect-ratio:8/5;min-height:400px;border-radius:8px;';
      scene.appendChild(canvas);
    }

    var px = Math.max(0, Math.min(98, cmd.x));
    var py = Math.max(0, Math.min(98, cmd.y));

    element.style.position = 'absolute';
    element.style.left = px + '%';
    element.style.top = py + '%';
    // Allow wider elements — cap at remaining space or 70%, whichever is smaller
    element.style.maxWidth = Math.min(70, 99 - px) + '%';
    element.style.zIndex = '2';
    element.classList.add('bd-positioned');

    canvas.appendChild(element);

    // No overlap nudging — the tutor has explicit x,y control and spacing guidance.
    // Post-render nudging was causing cascading displacement that destroyed layouts.
    return;
  }

  // ── Zone-based placement (left/right spatial positioning) ──
  if (placement === 'left' || placement === 'right') {
    endCurrentRowIfNeeded(placement);
    var grid = scene.querySelector('.bd-zone-grid:last-child');
    // Reuse the last grid if it exists and is the last child, otherwise create new
    if (!grid || grid !== scene.lastElementChild || grid.classList.contains('bd-grid-bg')) {
      grid = document.createElement('div');
      grid.className = 'bd-zone-grid';
      scene.appendChild(grid);
    }
    element.classList.add(placement === 'left' ? 'bd-zone-left' : 'bd-zone-right');
    grid.appendChild(element);
    return;
  }

  // If inside a columns grid, append there
  if (board.currentColumns && placement === 'below') {
    board.currentColumns.appendChild(element);
    return;
  }

  if (placement === 'below') {
    endCurrentRowIfNeeded(placement);
    scene.appendChild(element);
    return;
  }

  if (placement === 'center') {
    endCurrentRowIfNeeded(placement);
    element.classList.add('bd-placement-center');
    scene.appendChild(element);
    return;
  }

  if (placement === 'right-align') {
    endCurrentRowIfNeeded(placement);
    element.classList.add('bd-placement-right');
    scene.appendChild(element);
    return;
  }

  if (placement === 'indent') {
    endCurrentRowIfNeeded(placement);
    element.classList.add('bd-placement-indent');
    scene.appendChild(element);
    return;
  }

  if (placement === 'full-width') {
    endCurrentRowIfNeeded(placement);
    scene.appendChild(element);
    return;
  }

  if (placement === 'row-start') {
    endCurrentRowIfNeeded(placement);
    var row = document.createElement('div');
    row.className = 'bd-row';
    row.appendChild(element);
    scene.appendChild(row);
    board.currentRow = row;
    return;
  }

  if (placement === 'row-next') {
    if (!board.currentRow) {
      var row = document.createElement('div');
      row.className = 'bd-row';
      row.appendChild(element);
      scene.appendChild(row);
      board.currentRow = row;
    } else {
      board.currentRow.appendChild(element);
    }
    return;
  }

  if (placement.startsWith('beside:')) {
    var refId = placement.split(':')[1];
    var refEl = getElement(refId);
    if (refEl) {
      var parentRow = refEl.closest('.bd-row');
      if (parentRow) {
        parentRow.appendChild(element);
        board.currentRow = parentRow;
      } else {
        var row = document.createElement('div');
        row.className = 'bd-row';
        refEl.parentNode.insertBefore(row, refEl);
        row.appendChild(refEl);
        row.appendChild(element);
        board.currentRow = row;
      }
    } else {
      endCurrentRowIfNeeded(placement);
      scene.appendChild(element);
    }
    return;
  }

  if (placement.startsWith('below:')) {
    var refId = placement.split(':')[1];
    var refEl = getElement(refId);
    if (refEl) {
      // If ref is inside a .bd-row, create a vertical column wrapper
      // so stacked items stay in the row (e.g., legend items beside animation)
      var parentRow = refEl.closest('.bd-row');
      if (parentRow) {
        // Check if ref is already in a column wrapper
        var col = refEl.closest('.bd-column');
        if (!col) {
          // Wrap the ref element in a column
          col = document.createElement('div');
          col.className = 'bd-column';
          refEl.parentNode.insertBefore(col, refEl);
          col.appendChild(refEl);
        }
        // Append new element to the same column
        col.appendChild(element);
      } else {
        // Not in a row — insert after the ref element normally
        if (refEl.nextSibling) {
          refEl.parentNode.insertBefore(element, refEl.nextSibling);
        } else {
          refEl.parentNode.appendChild(element);
        }
      }
    } else {
      scene.appendChild(element);
    }
    return;
  }

  endCurrentRowIfNeeded(placement);
  scene.appendChild(element);
}

// ═══════════════════════════════════════════════════════════════
// 5. SCENE
// ═══════════════════════════════════════════════════════════════

function snapshotScene() {
  if (!board.liveScene) return;

  var scenesStack = document.getElementById('bd-scenes-stack');
  if (!scenesStack) return;

  var frozenScene = board.liveScene;
  frozenScene.removeAttribute('id');
  frozenScene.classList.add('bd-scene-frozen');
  frozenScene.dataset.sceneIndex = board.scenes.length;

  scenesStack.appendChild(frozenScene);
  board.scenes.push({ element: frozenScene });

  board.animations.forEach(function(entry) {
    try { entry.instance.noLoop(); } catch (e) {}
  });
  board.animations = [];

  var newScene = document.createElement('div');
  newScene.id = 'bd-live-scene';
  newScene.className = 'bd-scene';
  newScene.innerHTML = '<div class="bd-grid-bg"></div>';

  var boardContent = document.getElementById('bd-board-content');
  if (boardContent) {
    boardContent.appendChild(newScene);
  }

  board.liveScene = newScene;
  board.currentRow = null;
  board.animRetries.clear();
  board._userScrolledUp = false; // Reset scroll lock for new scene

  // Scroll to the new scene so content starts at the top of viewport
  var wrap = document.getElementById('bd-canvas-wrap');
  if (wrap) {
    requestAnimationFrame(function() {
      var sceneRect = newScene.getBoundingClientRect();
      var wrapRect = wrap.getBoundingClientRect();
      var targetTop = wrap.scrollTop + (sceneRect.top - wrapRect.top) - 20;
      wrap.scrollTo({ top: Math.max(0, targetTop), behavior: 'smooth' });
    });
  }

  console.log('[Scene] Snapshot ' + (board.scenes.length - 1) + ' — DOM preserved (no JPEG)');
}

function clearAll() {
  var scenesStack = document.getElementById('bd-scenes-stack');
  if (scenesStack) scenesStack.innerHTML = '';

  board.scenes = [];
  board.elements.clear();
  board.animations.forEach(function(a) { try { a.instance.remove(); } catch (e) {} });
  board.animations = [];
  board.animRetries.clear();
  endRow();

  if (board.liveScene) {
    board.liveScene.innerHTML = '<div class="bd-grid-bg"></div>';
  }
}

function updateAnimationVisibility() {
  var wrap = document.getElementById('bd-canvas-wrap');
  if (!wrap) return;

  var wrapRect = wrap.getBoundingClientRect();
  var margin = 200;

  board.animations.forEach(function(entry) {
    if (!entry.container || !entry.instance) return;
    var rect = entry.container.getBoundingClientRect();
    var visible = rect.bottom > wrapRect.top - margin &&
                  rect.top < wrapRect.bottom + margin;

    try {
      if (visible && !entry._running) {
        entry.instance.loop();
        entry._running = true;
      } else if (!visible && entry._running !== false) {
        entry.instance.noLoop();
        entry._running = false;
      }
    } catch (e) {}
  });
}

// ═══════════════════════════════════════════════════════════════
// 6. HIGHLIGHT
// ═══════════════════════════════════════════════════════════════

function zoomPulse(elementId) {
  var entry = board.elements.get(elementId);
  if (!entry) {
    console.warn('[Ref] Element not found:', elementId,
      '— available:', Array.from(board.elements.keys()).join(', '));
    return;
  }

  var el = entry.element;
  if (!el || !el.isConnected) return;

  el.classList.add('bd-highlight');
  el.scrollIntoView({ behavior: 'smooth', block: 'center' });

  setTimeout(function() {
    el.classList.remove('bd-highlight');
  }, 4300);
}

function scrollToElement(elementId) {
  var entry = board.elements.get(elementId);
  if (!entry || !entry.element || !entry.element.isConnected) return;
  entry.element.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// ═══════════════════════════════════════════════════════════════
// 7. ANIMATION
// ═══════════════════════════════════════════════════════════════

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

  var stack = [];
  var inStr = false, esc = false;
  for (var i = 0; i < code.length; i++) {
    var ch = code[i];
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

  code = code.replace(/\b(let|const|var)\s+(W|H)\b\s*=/g, '$2 =');
  code = code.replace(/\b(let|const|var)\s+S\b\s*=/g, 'S =');

  // Fix "Function statements require a function name" —
  // LLM sometimes wraps code in function(p,W,H){...} which is invalid
  // as a statement. Convert to IIFE or strip the wrapper.
  code = code.trim();
  if (/^function\s*\(/.test(code)) {
    // Anonymous function wrapper — convert to IIFE
    code = '(' + code + ')(p, W, H);';
  }

  return code;
}

function buildControlBridge(scale, isWebGL) {
  return '\n' +
    '    var _controlParams = {};\n' +
    '    var S = ' + scale.toFixed(2) + ';\n' +
    '    function onControl(params) {\n' +
    '      if (params._unhighlight) { _controlParams._highlight = null; }\n' +
    '      Object.assign(_controlParams, params);\n' +
    '      if (p._animHelper && p._animHelper._onControl) { p._animHelper._onControl(params); }\n' +
    '    }\n' +
    '    p._onControl = function(params) { onControl(params); };\n' +
    '    function sTextSize(sz) { return sz * S; }\n' +
    '    function sStroke(w) { return Math.max(1, w * S); }\n' +
    '    function applyHighlight(p, color, isHighlighted) {\n' +
    '      if (isHighlighted) { p.strokeWeight(sStroke(3)); p.drawingContext.shadowColor = color || \'#34d399\'; p.drawingContext.shadowBlur = 18 * S; }\n' +
    '      else { p.strokeWeight(sStroke(1.5)); p.drawingContext.shadowBlur = 0; }\n' +
    '    }\n' +
    '    [\'setLineDash\',\'getLineDash\',\'setTransform\',\'resetTransform\',\'clip\',\'clearRect\',\n' +
    '     \'createLinearGradient\',\'createRadialGradient\',\'measureText\',\'fillRect\',\'strokeRect\'].forEach(function(m) {\n' +
    '      p[m] = function() {\n' +
    '        if (p.drawingContext && typeof p.drawingContext[m] === \'function\') {\n' +
    '          return p.drawingContext[m].apply(p.drawingContext, arguments);\n' +
    '        }\n' +
    '      };\n' +
    '    });\n' +
    (isWebGL ? '\n    p.text = function() {};\n    p.textFont = function() {};\n    p.textSize = function() {};\n    p.textAlign = function() {};\n' : '') +
    '  ';
}

// ── Animation Fullscreen Toggle ──
function toggleAnimFullscreen(figure, animBox) {
  if (figure.classList.contains('bd-anim-fullscreen')) {
    // Restore
    figure.classList.remove('bd-anim-fullscreen');
    // Remove backdrop overlay
    var backdrop = figure.querySelector('.bd-anim-backdrop');
    if (backdrop) backdrop.remove();
    // Remove close button
    var closeBtn = figure.querySelector('.bd-anim-close-btn');
    if (closeBtn) closeBtn.remove();
    // Remove escape handler
    if (figure._escHandler) {
      document.removeEventListener('keydown', figure._escHandler);
      figure._escHandler = null;
    }
    // Update expand button
    var btn = animBox.querySelector('.bd-anim-expand-btn');
    if (btn) { btn.textContent = '\u26F6'; btn.title = 'Expand'; }
    // Resize p5 back
    var inst = animBox._p5Instance;
    if (inst && typeof inst.resizeCanvas === 'function') {
      requestAnimationFrame(function() {
        var r = animBox.getBoundingClientRect();
        try { inst.resizeCanvas(Math.round(r.width), Math.round(r.height)); } catch(e) {}
      });
    }
  } else {
    // Expand to fullscreen
    figure.classList.add('bd-anim-fullscreen');
    // Add backdrop overlay (click to close)
    var backdrop = document.createElement('div');
    backdrop.className = 'bd-anim-backdrop';
    backdrop.addEventListener('click', function() { toggleAnimFullscreen(figure, animBox); });
    figure.insertBefore(backdrop, figure.firstChild);
    // Add visible close button
    var closeBtn = document.createElement('button');
    closeBtn.className = 'bd-anim-close-btn';
    closeBtn.textContent = '\u2715';
    closeBtn.title = 'Close fullscreen';
    closeBtn.addEventListener('click', function() { toggleAnimFullscreen(figure, animBox); });
    figure.appendChild(closeBtn);
    // Update expand button
    var btn = animBox.querySelector('.bd-anim-expand-btn');
    if (btn) { btn.textContent = '\u2715'; btn.title = 'Restore'; }
    // Resize p5 — delay to let CSS transition complete
    var inst = animBox._p5Instance;
    if (inst && typeof inst.resizeCanvas === 'function') {
      setTimeout(function() {
        var r = animBox.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) {
          try { inst.resizeCanvas(Math.round(r.width), Math.round(r.height)); } catch(e) {}
        }
      }, 100);
    }
    // Escape key closes fullscreen
    figure._escHandler = function(e) {
      if (e.key === 'Escape') { toggleAnimFullscreen(figure, animBox); }
    };
    document.addEventListener('keydown', figure._escHandler);
  }
}

function createAnimation(cmd) {
  if (!cmd.code) return;

  // ── Build the figure container (like matplotlib figure with title + legend) ──
  var figure = document.createElement('div');
  figure.className = 'bd-el bd-anim-figure';
  if (cmd.id) figure.id = cmd.id;
  figure.dataset.cmd = 'animation';

  // Title bar (like plt.title) — rendered above the canvas
  if (cmd.title || cmd.text) {
    var titleBar = document.createElement('div');
    titleBar.className = 'bd-anim-title bd-chalk-cyan bd-size-small';
    titleBar.textContent = cmd.title || cmd.text || '';
    figure.appendChild(titleBar);
  }

  // Animation box (canvas area)
  var el = document.createElement('div');
  el.className = 'bd-anim-box';

  // Controls: expand + restore
  var controls = document.createElement('div');
  controls.className = 'bd-anim-controls';
  var expandBtn = document.createElement('button');
  expandBtn.className = 'bd-anim-expand-btn';
  expandBtn.textContent = '\u26F6';
  expandBtn.title = 'Expand animation';
  expandBtn.addEventListener('click', function() {
    toggleAnimFullscreen(figure, el);
  });
  controls.appendChild(expandBtn);
  el.appendChild(controls);

  var canvasWrap = document.createElement('div');
  canvasWrap.className = 'bd-anim-canvas-wrap';
  canvasWrap.style.cssText = 'width:100%;height:100%;overflow:hidden;border-radius:0 0 4px 4px;';
  el.appendChild(canvasWrap);

  var animH = cmd.h || 280;
  var animW = cmd.w || 420;
  el.style.minHeight = animH + 'px';
  el.style.aspectRatio = (animW / animH).toFixed(3);

  figure.appendChild(el);

  // Bottom legend bar disabled — AnimHelper A.legend() renders glass overlay inside canvas
  // if (cmd.legend && Array.isArray(cmd.legend) && cmd.legend.length > 0) { ... }

  // Place the self-contained figure
  placeElement(figure, cmd.placement, cmd);
  // Register for {ref:id}
  if (cmd.id) registerElement(cmd.id, figure);

  // Now measure actual rendered size
  var elRect = el.getBoundingClientRect();
  var pw = Math.round(elRect.width) || animW;
  var ph = Math.round(elRect.height) || animH;

  var isWebGL = /p\.WEBGL|,\s*WEBGL/.test(cmd.code);
  var scale = pw / 300;
  var code = sanitizeCode(cmd.code);
  code = code.replace(/p\.textSize\((\d+(?:\.\d+)?)\)/g, function(_, n) { return 'p.textSize(' + n + ' * S)'; });
  code = code.replace(/p\.strokeWeight\((\d+(?:\.\d+)?)\)/g, function(_, n) { return 'p.strokeWeight(Math.max(1, ' + n + ' * S))'; });
  var fullCode = buildControlBridge(scale, isWebGL) + '\n' + code;

  var sketchFn;
  try {
    sketchFn = new Function('p', 'W', 'H', fullCode);
  } catch (e) {
    try {
      sketchFn = new Function('p', 'W', 'H', fullCode.replace(/[^\x00-\x7F]/g, ''));
    } catch (e2) {
      console.warn('[Animation] Compile error — calling syntax fix:', e.message);
      showSkeleton(el, canvasWrap, cmd, e.message, scale, isWebGL);
      return;
    }
  }

  var inst;
  try {
    inst = new p5(function(p) {
      try { sketchFn(p, pw, ph); } catch (err) {
        console.warn('[Animation] Sketch runtime error (Haiku fix disabled):', err.message);
        canvasWrap.innerHTML = '<div style="padding:12px;color:rgba(248,113,113,0.4);font-size:12px;font-family:monospace">Animation error</div>';
        return;
      }
      var userDraw = p.draw;
      if (userDraw) {
        var errors = 0;
        p.draw = function () {
          try { userDraw.call(p); } catch (err) {
            if (++errors === 1) console.log('[Animation] draw() has a minor error (animation still runs):', err.message);
            if (errors >= 30) p.noLoop(); // Stop sooner to save CPU
          }
        };
      }
      var userSetup = p.setup;
      p.setup = function () {
        if (userSetup) userSetup.call(p);
        try { if (!p._renderer.isP3D) p.textFont('sans-serif'); } catch (e) {}
        // Auto-inject AnimHelper if LLM didn't create one
        if (!p._animHelper && typeof AnimHelper !== 'undefined' && !(p._renderer && p._renderer.isP3D)) {
          try {
            var _a = new AnimHelper(p, p.width, p.height);
            p._animHelper = _a;
            console.log('[Animation] AnimHelper auto-injected');
          } catch (e) { console.warn('[Animation] AnimHelper auto-inject failed:', e); }
        }
      };
      // Note: anim-control forwarding to AnimHelper is handled by buildControlBridge's onControl()
    }, canvasWrap);
  } catch (e) {
    console.warn('[Animation] Init error (Haiku fix disabled):', e.message);
    canvasWrap.innerHTML = '<div style="padding:12px;color:rgba(248,113,113,0.4);font-size:12px;font-family:monospace">Animation init error</div>';
    return;
  }

  el._p5Instance = inst;
  var entry = { container: el, instance: inst, _running: true };
  board.animations.push(entry);

  // Blank detection disabled — Haiku fix causes more harm than good
  // var retryKey = cmd.id || 'anon';
  // var attempt = board.animRetries.get(retryKey) || 0;
  // if (attempt < 1) {
  //   setTimeout(function() { detectBlank(canvasWrap, entry, cmd, retryKey, attempt); }, 2500);
  // }
}

function detectBlank(canvasWrap, entry, cmd, retryKey, attempt) {
  try {
    var cvs = canvasWrap.querySelector('canvas');
    if (!cvs || cvs.width === 0) return;
    var ctx = cvs.getContext('2d', { willReadFrequently: true });
    if (!ctx) return;
    var data = ctx.getImageData(0, 0, cvs.width, cvs.height).data;
    var step = Math.max(4, Math.floor(data.length / 200)) & ~3;
    var bright = 0;
    for (var i = 0; i < data.length; i += step) {
      if (data[i] > 25 || data[i + 1] > 30 || data[i + 2] > 25) bright++;
    }
    if (bright >= 3) return;

    board.animRetries.set(retryKey, attempt + 1);
    console.warn('[Animation] Blank detected — calling Haiku fix:', retryKey);

    fetch(board.apiUrl + '/api/fix-animation', {
      method: 'POST',
      headers: Object.assign({ 'Content-Type': 'application/json' }, board.getAuthHeaders ? board.getAuthHeaders() : {}),
      body: JSON.stringify({ code: cmd.code, error: 'Canvas all black. Fix drawing logic.' }),
    })
      .then(function(r) { return r.ok ? r.json() : null; })
      .then(function(data) {
        if (!data || !data.code) throw new Error('No code');
        try { entry.instance.remove(); } catch (e) {}
        // Remove the ENTIRE figure element (not just canvas container)
        var fig = entry.container && entry.container.closest('.bd-anim-figure');
        if (fig && fig.parentNode) fig.parentNode.removeChild(fig);
        else if (entry.container && entry.container.parentNode) entry.container.parentNode.removeChild(entry.container);
        var idx = board.animations.indexOf(entry);
        if (idx >= 0) board.animations.splice(idx, 1);
        // Mark as retried so it won't trigger another blank detection
        board.animRetries.set(retryKey, 99);
        createAnimation(Object.assign({}, cmd, { code: data.code }));
      })
      .catch(function() {
        try { entry.instance.remove(); } catch (e) {}
        var fig = entry.container && entry.container.closest('.bd-anim-figure');
        if (fig && fig.parentNode) fig.parentNode.removeChild(fig);
        else if (entry.container && entry.container.parentNode) entry.container.parentNode.removeChild(entry.container);
        var idx = board.animations.indexOf(entry);
        if (idx >= 0) board.animations.splice(idx, 1);
      });
  } catch (e) {}
}

function showSkeleton(el, canvasWrap, cmd, errorMsg, scale, isWebGL) {
  canvasWrap.innerHTML =
    '<div style="width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;min-height:150px">' +
    '<div style="width:36px;height:36px;border:2px solid rgba(52,211,153,0.3);border-top-color:rgba(52,211,153,0.8);border-radius:50%;animation:spin 1s linear infinite"></div>' +
    '<div style="color:rgba(52,211,153,0.5);font-size:12px;font-family:monospace">fixing animation...</div>' +
    '</div>' +
    '<style>@keyframes spin{to{transform:rotate(360deg)}}</style>';

  fetch(board.apiUrl + '/api/fix-animation', {
    method: 'POST',
    headers: Object.assign({ 'Content-Type': 'application/json' }, board.getAuthHeaders ? board.getAuthHeaders() : {}),
    body: JSON.stringify({ code: cmd.code, error: errorMsg }),
  })
    .then(function(r) { return r.ok ? r.json() : null; })
    .then(function(data) {
      if (!data || !data.code) throw new Error('No code');
      canvasWrap.innerHTML = '';
      var fixedCode = sanitizeCode(data.code);
      var fullCode = buildControlBridge(scale, isWebGL) + '\n' + fixedCode;
      var fn = new Function('p', 'W', 'H', fullCode);
      var rect = el.getBoundingClientRect();
      var inst = new p5(function(p) {
        try { fn(p, Math.round(rect.width) || 300, Math.round(rect.height) || 200); } catch (e) {
          canvasWrap.innerHTML = '<div style="padding:12px;color:rgba(255,255,255,0.2);font-size:12px">Animation unavailable</div>';
          return;
        }
        var userSetup = p.setup;
        p.setup = function () {
          if (userSetup) userSetup.call(p);
          try { if (!p._renderer.isP3D) p.textFont('sans-serif'); } catch (e) {}
          if (!p._animHelper && typeof AnimHelper !== 'undefined' && !(p._renderer && p._renderer.isP3D)) {
            try { p._animHelper = new AnimHelper(p, p.width, p.height); } catch (e) {}
          }
        };
      }, canvasWrap);
      el._p5Instance = inst;
      board.animations.push({ container: el, instance: inst, _running: true });
    })
    .catch(function() {
      if (el.parentNode) el.parentNode.removeChild(el);
    });
}

// ═══════════════════════════════════════════════════════════════
// 8. COMMANDS
// ═══════════════════════════════════════════════════════════════

async function runCommand(cmd) {
  if (board.cancelFlag) return;
  // Pause: wait while pauseFlag is set (check every 100ms)
  while (board.pauseFlag && !board.cancelFlag) {
    await new Promise(r => setTimeout(r, 100));
  }
  if (board.cancelFlag) return;
  if (!board.liveScene) return;

  var contentCmds = ['text', 'latex', 'animation', 'equation', 'compare', 'step',
    'check', 'cross', 'callout', 'list', 'divider', 'result', 'mermaid', 'diagram',
    'line', 'arrow', 'rect', 'fillrect', 'circle', 'arc', 'dot', 'dashed'];
  if (!cmd.placement && contentCmds.includes(cmd.cmd)) {
    cmd.placement = 'below';
  }

  switch (cmd.cmd) {
    case 'text':     await renderText(cmd); break;
    case 'latex':    await renderText(cmd); break;
    case 'equation': await renderEquation(cmd); break;
    case 'compare':  await renderCompare(cmd); break;
    case 'step':     await renderStep(cmd); break;
    case 'check':    await renderCheckCross(cmd, true); break;
    case 'cross':    await renderCheckCross(cmd, false); break;
    case 'callout':  await renderCallout(cmd); break;
    case 'connect':  renderConnect(cmd); break;
    case 'mermaid':  await renderMermaid(cmd); break;
    case 'list':     await renderList(cmd); break;
    case 'divider':  renderDivider(cmd); break;
    case 'result':   await renderResult(cmd); break;
    case 'animation': await createAnimation(cmd); break;
    case 'diagram':  await renderDiagram(cmd); break;
    case 'columns':  renderColumns(cmd); break;
    case 'columns-end': renderColumnsEnd(); break;
    case 'annotate': renderAnnotate(cmd); break;
    case 'assess-mcq': renderBoardMCQ(cmd); break;
    case 'assess-freetext': renderBoardFreetext(cmd); break;
    case 'assess-spot-error': renderBoardSpotError(cmd); break;
    case 'assess-teachback': renderBoardTeachback(cmd); break;
    case 'assess-confidence': renderBoardConfidence(cmd); break;
    case 'strikeout': renderStrikeout(cmd); break;
    case 'update':   await renderUpdate(cmd); break;
    case 'delete':   renderDelete(cmd); break;
    case 'clone':    await renderClone(cmd); break;
    case 'clear':    clearAll(); break;

    // SVG shape primitives — rendered as inline SVG elements
    case 'line':     renderSvgLine(cmd); break;
    case 'arrow':    renderSvgArrow(cmd); break;
    case 'rect':     renderSvgRect(cmd); break;
    case 'fillrect': renderSvgRect(cmd); break;
    case 'circle':   renderSvgCircle(cmd); break;
    case 'arc':      renderSvgCircle(cmd); break;
    case 'dot':      renderSvgDot(cmd); break;
    case 'dashed':   renderSvgLine(cmd); break;
    case 'freehand': break; // not supported in DOM — use animation
    case 'curvedarrow': renderSvgArrow(cmd); break;
    case 'brace':    break;
    case 'matrix':   break;
    case 'voice':    break;
    case 'pause':    break;
    case 'code':     await renderCode(cmd); break;
    case 'scene3d':  await renderScene3D(cmd); break;
    default:
      console.warn('[Board] Unknown command:', cmd.cmd);
  }

  autoScroll();
}

// ── Code block (syntax-highlighted, read-only) ──────────────────────
async function renderCode(cmd) {
  var el = createElement('div', cmd, 'bd-code-block');
  var header = document.createElement('div');
  header.className = 'bd-code-header';
  header.innerHTML = '<span class="bd-code-lang">' + (cmd.lang || 'code').toUpperCase() + '</span>';
  if (cmd.filename) header.innerHTML += '<span class="bd-code-file">' + cmd.filename + '</span>';
  el.appendChild(header);

  var body = document.createElement('pre');
  body.className = 'bd-code-body';
  var lines = (cmd.text || '').split('\n');
  var highlight = cmd.highlight || [];
  body.innerHTML = lines.map(function(line, i) {
    var lineNum = i + 1;
    var cls = highlight.includes(lineNum) ? 'bd-cl bd-cl-hi' : 'bd-cl';
    return '<span class="' + cls + '"><span class="bd-ln">' + lineNum + '</span>' + escapeHtml(line) + '</span>';
  }).join('\n');
  el.appendChild(body);

  placeElement(el, cmd.placement, cmd);
}

function escapeHtml(t) {
  return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── Three.js 3D scene ───────────────────────────────────────────────
async function renderScene3D(cmd) {
  // Show skeleton placeholder immediately
  var container = createElement('div', cmd, 'bd-scene3d');
  container.style.width = (cmd.width || 400) + 'px';
  container.style.height = (cmd.height || 300) + 'px';
  container.style.borderRadius = '10px';
  container.style.overflow = 'hidden';
  container.style.border = '1px solid rgba(255,255,255,0.08)';
  container.style.background = '#0a0c10';
  container.style.position = 'relative';
  placeElement(container, cmd.placement, cmd);

  // Skeleton animation while loading
  container.innerHTML = '<div class="bd-3d-skeleton"><div class="bd-3d-skeleton-orb"></div><span>' + (cmd.title || 'Loading 3D scene...') + '</span></div>';

  if (typeof THREE === 'undefined') {
    console.warn('[Board] Three.js not loaded — showing fallback');
    container.innerHTML = '<div class="bd-3d-fallback">' +
      '<div class="bd-3d-fallback-icon">&#9674;</div>' +
      '<span>3D: ' + (cmd.title || 'visualization') + '</span>' +
      '<span class="bd-3d-fallback-sub">Interactive 3D not available</span></div>';
    return;
  }

  // Clear skeleton, set up Three.js
  container.innerHTML = '';
  var w = cmd.width || 400, h = cmd.height || 300;
  var scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0a0c10);
  var camera = new THREE.PerspectiveCamera(50, w / h, 0.1, 1000);
  camera.position.set(cmd.cameraX || 3, cmd.cameraY || 2, cmd.cameraZ || 5);
  camera.lookAt(0, 0, 0);

  var renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(w, h);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  container.appendChild(renderer.domElement);

  // Orbit controls for interaction
  if (THREE.OrbitControls) {
    var controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.autoRotate = cmd.autoRotate !== false;
    controls.autoRotateSpeed = cmd.rotateSpeed || 1;
  }

  // Lighting
  var ambient = new THREE.AmbientLight(0x404040, 0.6);
  scene.add(ambient);
  var dir = new THREE.DirectionalLight(0xffffff, 0.8);
  dir.position.set(5, 5, 5);
  scene.add(dir);

  // Grid helper
  if (cmd.grid !== false) {
    var grid = new THREE.GridHelper(10, 10, 0x1a3a2a, 0x111413);
    scene.add(grid);
  }

  // Axes helper
  if (cmd.axes !== false) {
    var axes = new THREE.AxesHelper(2);
    scene.add(axes);
  }

  // Execute the setup code (LLM-generated Three.js code)
  if (cmd.code) {
    try {
      var setupFn = new Function('THREE', 'scene', 'camera', 'renderer', cmd.code);
      setupFn(THREE, scene, camera, renderer);
    } catch (e) {
      console.error('[Board] scene3d code error:', e);
      // Auto-fix via Haiku — same as p5 animation fix but for Three.js
      if (board.apiUrl) {
        fetch(board.apiUrl + '/api/fix-animation', {
          method: 'POST',
          headers: Object.assign({ 'Content-Type': 'application/json' }, board.getAuthHeaders ? board.getAuthHeaders() : {}),
          body: JSON.stringify({ code: cmd.code, error: e.message, type: 'threejs' }),
        })
          .then(function(r) { return r.ok ? r.json() : null; })
          .then(function(data) {
            if (!data || !data.code) return;
            try {
              // Clear scene objects (except camera, lights, axes)
              var toRemove = [];
              scene.traverse(function(obj) {
                if (obj !== scene && obj !== camera && obj.type !== 'AmbientLight' && obj.type !== 'DirectionalLight' && obj.type !== 'AxesHelper') {
                  toRemove.push(obj);
                }
              });
              toRemove.forEach(function(obj) { scene.remove(obj); });
              // Re-execute with fixed code
              var fixedFn = new Function('THREE', 'scene', 'camera', 'renderer', data.code);
              fixedFn(THREE, scene, camera, renderer);
              console.log('[Board] scene3d fixed by Haiku');
            } catch (e2) {
              console.error('[Board] scene3d fix also failed:', e2);
            }
          })
          .catch(function() {});
      }
    }
  }

  // Animation loop
  var animId;
  function animate() {
    animId = requestAnimationFrame(animate);
    if (controls) controls.update();
    renderer.render(scene, camera);
  }
  animate();

  // Store for cleanup
  board.animations.push({
    instance: {
      remove: function() { cancelAnimationFrame(animId); renderer.dispose(); },
      noLoop: function() { cancelAnimationFrame(animId); }
    }
  });
}

// ── COLUMNS (grid layout zone) ──

function renderColumns(cmd) {
  var scene = board.liveScene;
  if (!scene) return;
  board.currentRow = null;

  var cols = cmd.cols || 2;
  var grid = document.createElement('div');
  grid.className = 'bd-el bd-columns';
  grid.style.gridTemplateColumns = 'repeat(' + cols + ', 1fr)';
  if (cmd.id) grid.id = cmd.id;
  scene.appendChild(grid);
  board.currentColumns = grid;
}

function renderColumnsEnd() {
  board.currentColumns = null;
}

// ── ANNOTATE (relative label on existing element) ──

function renderAnnotate(cmd) {
  if (!cmd.target || !cmd.text) return;
  var target = document.getElementById(cmd.target) || (board.elements.get(cmd.target) || {}).element;
  if (!target) {
    // Fallback: render as dim text
    var el = createStyledElement('div', { text: cmd.text, color: cmd.color || 'dim', size: 'small' }, 'bd-text');
    placeElement(el, 'below', cmd);
    animateText(el, cmd.text, { charDelay: 20 });
    return;
  }

  var ann = document.createElement('span');
  ann.className = 'bd-annotation bd-chalk-' + (cmd.color || 'dim');
  ann.textContent = cmd.text;

  var pos = cmd.pos || 'right';
  ann.classList.add('bd-ann-' + pos);

  if (pos === 'right' || pos === 'beside') {
    var row = target.closest('.bd-row');
    if (row) {
      row.appendChild(ann);
    } else {
      var newRow = document.createElement('div');
      newRow.className = 'bd-row';
      target.parentNode.insertBefore(newRow, target);
      newRow.appendChild(target);
      newRow.appendChild(ann);
    }
  } else {
    var wrapper = target.closest('.bd-row') || target;
    if (wrapper.nextSibling) {
      wrapper.parentNode.insertBefore(ann, wrapper.nextSibling);
    } else {
      wrapper.parentNode.appendChild(ann);
    }
  }
}

// ═══════════════════════════════════════════════════════════════
// BOARD-NATIVE ASSESSMENT ELEMENTS
// Interactive assessment rendered directly on the board canvas.
// ═══════════════════════════════════════════════════════════════

function renderBoardMCQ(cmd) {
  var el = document.createElement('div');
  el.className = 'bd-el bd-assess-card';
  if (cmd.id) el.id = cmd.id;

  var prompt = document.createElement('div');
  prompt.className = 'bd-assess-prompt';
  prompt.textContent = cmd.prompt || cmd.text || '';
  el.appendChild(prompt);

  var options = cmd.options || [];
  var optionsWrap = document.createElement('div');
  optionsWrap.className = 'bd-mcq-options';

  options.forEach(function(opt, i) {
    var optEl = document.createElement('div');
    optEl.className = 'bd-mcq-opt';
    optEl.dataset.value = opt.value || String.fromCharCode(97 + i);
    optEl.dataset.correct = opt.correct ? 'true' : 'false';

    var radio = document.createElement('div');
    radio.className = 'bd-mcq-radio';
    optEl.appendChild(radio);

    var label = document.createElement('span');
    label.textContent = opt.text || opt.label || '';
    optEl.appendChild(label);

    optEl.addEventListener('click', function() {
      optionsWrap.querySelectorAll('.bd-mcq-opt').forEach(function(o) { o.classList.remove('bd-selected'); });
      optEl.classList.add('bd-selected');
    });

    optionsWrap.appendChild(optEl);
  });

  el.appendChild(optionsWrap);

  // Progress dots
  if (cmd.progress) {
    var dots = document.createElement('div');
    dots.className = 'bd-assess-progress';
    for (var pi = 0; pi < (cmd.progress.total || 3); pi++) {
      var dot = document.createElement('div');
      dot.className = 'bd-prog-dot' + (pi < (cmd.progress.done || 0) ? ' bd-prog-done' : pi === (cmd.progress.done || 0) ? ' bd-prog-active' : '');
      dots.appendChild(dot);
    }
    el.appendChild(dots);
  }

  // Submit button
  var submitWrap = document.createElement('div');
  submitWrap.className = 'bd-assess-submit';
  var submitBtn = document.createElement('button');
  submitBtn.className = 'bd-submit-btn';
  submitBtn.textContent = 'Submit';
  submitBtn.addEventListener('click', function() {
    var selected = optionsWrap.querySelector('.bd-mcq-opt.bd-selected');
    if (!selected) return;
    var isCorrect = selected.dataset.correct === 'true';
    selected.classList.add(isCorrect ? 'bd-correct' : 'bd-wrong');
    if (!isCorrect) {
      var correct = optionsWrap.querySelector('.bd-mcq-opt[data-correct="true"]');
      if (correct) correct.classList.add('bd-correct');
    }
    submitBtn.style.display = 'none';
    // Send answer to tutor
    if (typeof streamADK === 'function') {
      var ansText = selected.querySelector('span').textContent;
      streamADK(ansText, false, false);
    }
  });
  submitWrap.appendChild(submitBtn);
  el.appendChild(submitWrap);

  placeElement(el, cmd.placement || 'below', cmd);
}

function renderBoardFreetext(cmd) {
  var el = document.createElement('div');
  el.className = 'bd-el bd-assess-card';
  if (cmd.id) el.id = cmd.id;

  var prompt = document.createElement('div');
  prompt.className = 'bd-assess-prompt';
  prompt.textContent = cmd.prompt || cmd.text || '';
  el.appendChild(prompt);

  var input = document.createElement('textarea');
  input.className = 'bd-free-input';
  input.placeholder = cmd.placeholder || 'Type your answer...';
  input.rows = 4;
  el.appendChild(input);

  var submitWrap = document.createElement('div');
  submitWrap.className = 'bd-assess-submit';
  var submitBtn = document.createElement('button');
  submitBtn.className = 'bd-submit-btn';
  submitBtn.textContent = 'Submit';
  submitBtn.addEventListener('click', function() {
    var answer = input.value.trim();
    if (!answer) return;
    input.disabled = true;
    submitBtn.style.display = 'none';
    if (typeof streamADK === 'function') streamADK(answer, false, false);
  });
  submitWrap.appendChild(submitBtn);
  el.appendChild(submitWrap);

  placeElement(el, cmd.placement || 'below', cmd);
  setTimeout(function() { input.focus(); }, 300);
}

function renderBoardSpotError(cmd) {
  var el = document.createElement('div');
  el.className = 'bd-el bd-assess-card';
  if (cmd.id) el.id = cmd.id;

  var prompt = document.createElement('div');
  prompt.className = 'bd-assess-prompt';
  prompt.textContent = cmd.prompt || 'What\'s wrong with this?';
  el.appendChild(prompt);

  if (cmd.quote) {
    var quote = document.createElement('div');
    quote.className = 'bd-spot-error-eq';
    quote.textContent = cmd.quote;
    el.appendChild(quote);
  }

  if (cmd.hint) {
    var hint = document.createElement('div');
    hint.className = 'bd-assess-hint';
    hint.textContent = cmd.hint;
    el.appendChild(hint);
  }

  var input = document.createElement('textarea');
  input.className = 'bd-free-input';
  input.placeholder = 'Explain what\'s wrong and why it matters...';
  input.rows = 3;
  el.appendChild(input);

  var submitWrap = document.createElement('div');
  submitWrap.className = 'bd-assess-submit';
  var submitBtn = document.createElement('button');
  submitBtn.className = 'bd-submit-btn';
  submitBtn.textContent = 'Submit';
  submitBtn.addEventListener('click', function() {
    var answer = input.value.trim();
    if (!answer) return;
    input.disabled = true;
    submitBtn.style.display = 'none';
    if (typeof streamADK === 'function') streamADK(answer, false, false);
  });
  submitWrap.appendChild(submitBtn);
  el.appendChild(submitWrap);

  placeElement(el, cmd.placement || 'below', cmd);
}

function renderBoardTeachback(cmd) {
  var el = document.createElement('div');
  el.className = 'bd-el bd-assess-card';
  if (cmd.id) el.id = cmd.id;

  var label = document.createElement('div');
  label.className = 'bd-teachback-label';
  label.textContent = 'Your turn to teach';
  el.appendChild(label);

  var prompt = document.createElement('div');
  prompt.className = 'bd-assess-prompt';
  prompt.textContent = cmd.prompt || '';
  el.appendChild(prompt);

  var input = document.createElement('textarea');
  input.className = 'bd-free-input';
  input.placeholder = cmd.placeholder || 'Explain in your own words — pretend you\'re teaching a friend...';
  input.rows = 5;
  el.appendChild(input);

  var submitWrap = document.createElement('div');
  submitWrap.className = 'bd-assess-submit';
  var submitBtn = document.createElement('button');
  submitBtn.className = 'bd-submit-btn';
  submitBtn.textContent = 'Submit';
  submitBtn.addEventListener('click', function() {
    var answer = input.value.trim();
    if (!answer) return;
    input.disabled = true;
    submitBtn.style.display = 'none';
    if (typeof streamADK === 'function') streamADK(answer, false, false);
  });
  submitWrap.appendChild(submitBtn);
  el.appendChild(submitWrap);

  placeElement(el, cmd.placement || 'below', cmd);
  setTimeout(function() { input.focus(); }, 300);
}

function renderBoardConfidence(cmd) {
  var el = document.createElement('div');
  el.className = 'bd-el bd-assess-card';
  if (cmd.id) el.id = cmd.id;

  var prompt = document.createElement('div');
  prompt.className = 'bd-assess-prompt';
  prompt.textContent = cmd.prompt || 'How confident are you?';
  el.appendChild(prompt);

  var scale = document.createElement('div');
  scale.className = 'bd-confidence-scale';
  var levels = ['Not at all', 'A little', 'Fairly', 'Very confident'];
  levels.forEach(function(label) {
    var btn = document.createElement('button');
    btn.className = 'bd-conf-btn';
    btn.textContent = label;
    btn.addEventListener('click', function() {
      scale.querySelectorAll('.bd-conf-btn').forEach(function(b) { b.classList.remove('bd-conf-selected'); });
      btn.classList.add('bd-conf-selected');
      if (typeof streamADK === 'function') streamADK(label, false, false);
    });
    scale.appendChild(btn);
  });
  el.appendChild(scale);

  placeElement(el, cmd.placement || 'below', cmd);
}


// ── SVG Shape Primitives ──

function svgNS() { return 'http://www.w3.org/2000/svg'; }

function resolveColor(c) {
  var map = { white:'#e8e8e0', yellow:'#f5d97a', gold:'#fbbf24', green:'#34d399',
    blue:'#7eb8da', red:'#ff6b6b', cyan:'#53d8fb', dim:'#94a3b8' };
  return map[c] || c || '#e8e8e0';
}

// ── Helpers for canvas-based SVG drawing ──
function _ensureDrawCanvas(scene) {
  var canvas = scene.querySelector('.bd-draw-canvas');
  if (!canvas) {
    canvas = document.createElement('div');
    canvas.className = 'bd-draw-canvas';
    canvas.style.cssText = 'position:relative;width:100%;max-width:800px;margin:8px auto;' +
      'aspect-ratio:8/5;min-height:400px;border-radius:8px;';
    scene.appendChild(canvas);
  }
  return canvas;
}

function _ensureSvgOverlay(canvas) {
  var svgOverlay = canvas.querySelector('.bd-svg-overlay');
  if (!svgOverlay) {
    svgOverlay = document.createElementNS(svgNS(), 'svg');
    svgOverlay.classList.add('bd-svg-overlay');
    svgOverlay.setAttribute('viewBox', '0 0 100 100');
    svgOverlay.setAttribute('preserveAspectRatio', 'none');
    svgOverlay.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:1;';
    canvas.appendChild(svgOverlay);
  }
  return svgOverlay;
}

function renderSvgLine(cmd) {
  // If x,y coordinates present, render inside the drawing canvas using percentages
  if (typeof cmd.x1 === 'number' && typeof cmd.x2 === 'number') {
    var el = _renderCanvasLine(cmd);
    if (el) return;
  }
  // Fallback: flow-placed SVG
  var pad = 10, svgW = 200, svgH = 20;
  var svg = document.createElementNS(svgNS(), 'svg');
  svg.setAttribute('viewBox', '0 0 ' + svgW + ' ' + svgH);
  svg.setAttribute('width', Math.min(svgW, 500));
  svg.setAttribute('height', svgH);
  svg.style.cssText = 'display:block;overflow:visible;';
  var line = document.createElementNS(svgNS(), 'line');
  line.setAttribute('x1', pad); line.setAttribute('y1', svgH / 2);
  line.setAttribute('x2', svgW - pad); line.setAttribute('y2', svgH / 2);
  line.setAttribute('stroke', resolveColor(cmd.color));
  line.setAttribute('stroke-width', cmd.w || 2);
  if (cmd.cmd === 'dashed') line.setAttribute('stroke-dasharray', '8 4');
  line.setAttribute('stroke-linecap', 'round');
  svg.appendChild(line);
  var el = createElement('div', cmd, 'bd-svg-shape');
  el.appendChild(svg);
  placeElement(el, cmd.placement || 'below', cmd);
}

// Render line/arrow/shape inside the fixed drawing canvas using % coordinates
function _renderCanvasLine(cmd) {
  var scene = board.liveScene;
  if (!scene) return null;
  var canvas = _ensureDrawCanvas(scene);
  var svgOverlay = _ensureSvgOverlay(canvas);
  // Draw line using 0-100 percentage coordinates
  var x1 = cmd.x1 || 0, y1 = cmd.y1 || 0, x2 = cmd.x2 || 100, y2 = cmd.y2 || 0;
  var line = document.createElementNS(svgNS(), 'line');
  line.setAttribute('x1', x1); line.setAttribute('y1', y1);
  line.setAttribute('x2', x2); line.setAttribute('y2', y2);
  line.setAttribute('stroke', resolveColor(cmd.color));
  line.setAttribute('stroke-width', cmd.w || 2);
  if (cmd.cmd === 'dashed') line.setAttribute('stroke-dasharray', '4 3');
  line.setAttribute('stroke-linecap', 'round');
  line.setAttribute('vector-effect', 'non-scaling-stroke');
  svgOverlay.appendChild(line);
  return true; // consumed
}

function renderSvgArrow(cmd) {
  // If x,y coordinates present, render inside the drawing canvas
  if (typeof cmd.x1 === 'number' && typeof cmd.x2 === 'number') {
    var scene = board.liveScene;
    if (scene) {
      var canvas = _ensureDrawCanvas(scene);
      var svgOverlay = _ensureSvgOverlay(canvas);
      var x1 = cmd.x1 || 0, y1 = cmd.y1 || 0, x2 = cmd.x2 || 100, y2 = cmd.y2 || 0;
      var color = resolveColor(cmd.color);
      var markerId = 'arr-' + (cmd.id || Math.random().toString(36).slice(2));
      // Ensure defs exist
      var defs = svgOverlay.querySelector('defs');
      if (!defs) { defs = document.createElementNS(svgNS(), 'defs'); svgOverlay.prepend(defs); }
      var marker = document.createElementNS(svgNS(), 'marker');
      marker.setAttribute('id', markerId);
      marker.setAttribute('viewBox', '0 0 10 10');
      marker.setAttribute('refX', '10'); marker.setAttribute('refY', '5');
      marker.setAttribute('markerWidth', '6'); marker.setAttribute('markerHeight', '6');
      marker.setAttribute('orient', 'auto-start-reverse');
      var path = document.createElementNS(svgNS(), 'path');
      path.setAttribute('d', 'M 0 0 L 10 5 L 0 10 z');
      path.setAttribute('fill', color);
      marker.appendChild(path);
      defs.appendChild(marker);

      var line = document.createElementNS(svgNS(), 'line');
      line.setAttribute('x1', x1); line.setAttribute('y1', y1);
      line.setAttribute('x2', x2); line.setAttribute('y2', y2);
      line.setAttribute('stroke', color);
      line.setAttribute('stroke-width', cmd.w || 2);
      line.setAttribute('marker-end', 'url(#' + markerId + ')');
      line.setAttribute('vector-effect', 'non-scaling-stroke');
      svgOverlay.appendChild(line);
      return;
    }
  }
  // Fallback: flow-placed arrow
  var pad = 15, svgW = 200, svgH = 20;
  var color = resolveColor(cmd.color);
  var svg = document.createElementNS(svgNS(), 'svg');
  svg.setAttribute('viewBox', '0 0 ' + svgW + ' ' + svgH);
  svg.setAttribute('width', Math.min(svgW, 500));
  svg.setAttribute('height', svgH);
  svg.style.cssText = 'display:block;overflow:visible;';
  var markerId = 'arr-' + Math.random().toString(36).slice(2);
  var defs = document.createElementNS(svgNS(), 'defs');
  var marker = document.createElementNS(svgNS(), 'marker');
  marker.setAttribute('id', markerId);
  marker.setAttribute('viewBox', '0 0 10 10');
  marker.setAttribute('refX', '10'); marker.setAttribute('refY', '5');
  marker.setAttribute('markerWidth', '8'); marker.setAttribute('markerHeight', '8');
  marker.setAttribute('orient', 'auto-start-reverse');
  var mpath = document.createElementNS(svgNS(), 'path');
  mpath.setAttribute('d', 'M 0 0 L 10 5 L 0 10 z');
  mpath.setAttribute('fill', color);
  marker.appendChild(mpath);
  defs.appendChild(marker);
  svg.appendChild(defs);
  var line = document.createElementNS(svgNS(), 'line');
  line.setAttribute('x1', pad); line.setAttribute('y1', svgH / 2);
  line.setAttribute('x2', svgW - pad); line.setAttribute('y2', svgH / 2);
  line.setAttribute('stroke', color);
  line.setAttribute('stroke-width', cmd.w || 2);
  line.setAttribute('marker-end', 'url(#' + markerId + ')');
  svg.appendChild(line);
  var el = createElement('div', cmd, 'bd-svg-shape');
  el.appendChild(svg);
  placeElement(el, cmd.placement || 'below', cmd);
}

function renderSvgRect(cmd) {
  var color = resolveColor(cmd.color);

  // If x,y coordinates present, render inside the draw canvas SVG overlay
  if (typeof cmd.x === 'number' && typeof cmd.y === 'number') {
    var scene = board.liveScene;
    if (scene) {
      var canvas = scene.querySelector('.bd-draw-canvas') || _ensureDrawCanvas(scene);
      var svgOverlay = _ensureSvgOverlay(canvas);
      var rw = cmd.w || 15, rh = cmd.h || 10; // percentages in viewBox coords
      var rect = document.createElementNS(svgNS(), 'rect');
      rect.setAttribute('x', cmd.x); rect.setAttribute('y', cmd.y);
      rect.setAttribute('width', rw); rect.setAttribute('height', rh);
      rect.setAttribute('stroke', color);
      rect.setAttribute('stroke-width', cmd.lw || 1.5);
      rect.setAttribute('fill', cmd.cmd === 'fillrect' ? color : 'none');
      rect.setAttribute('rx', 1);
      rect.setAttribute('vector-effect', 'non-scaling-stroke');
      if (cmd.cmd === 'fillrect') rect.setAttribute('fill-opacity', '0.15');
      svgOverlay.appendChild(rect);
      return;
    }
  }

  // Flow-based placement fallback
  var rw = cmd.w || 100, rh = cmd.h || 60;
  var svg = document.createElementNS(svgNS(), 'svg');
  svg.setAttribute('viewBox', '0 0 ' + (rw + 4) + ' ' + (rh + 4));
  svg.setAttribute('width', Math.min(rw + 4, 500));
  svg.setAttribute('height', Math.min(rh + 4, 300));
  svg.style.cssText = 'display:block;';

  var rect = document.createElementNS(svgNS(), 'rect');
  rect.setAttribute('x', 2); rect.setAttribute('y', 2);
  rect.setAttribute('width', rw); rect.setAttribute('height', rh);
  rect.setAttribute('stroke', color);
  rect.setAttribute('stroke-width', cmd.lw || 1.5);
  rect.setAttribute('fill', cmd.cmd === 'fillrect' ? color : 'none');
  rect.setAttribute('rx', 3);
  if (cmd.cmd === 'fillrect') rect.setAttribute('fill-opacity', '0.15');
  svg.appendChild(rect);

  var el = createElement('div', cmd, 'bd-svg-shape');
  el.appendChild(svg);
  placeElement(el, cmd.placement || 'below', cmd);
}

function renderSvgCircle(cmd) {
  var color = resolveColor(cmd.color);

  // If x,y coordinates present, render inside the draw canvas SVG overlay
  if (typeof cmd.x === 'number' && typeof cmd.y === 'number') {
    var scene = board.liveScene;
    if (scene) {
      var canvas = scene.querySelector('.bd-draw-canvas') || _ensureDrawCanvas(scene);
      var svgOverlay = _ensureSvgOverlay(canvas);
      var r = cmd.r || 5; // percentage in viewBox coords
      var circle = document.createElementNS(svgNS(), 'circle');
      circle.setAttribute('cx', cmd.x); circle.setAttribute('cy', cmd.y);
      circle.setAttribute('r', r);
      circle.setAttribute('stroke', color);
      circle.setAttribute('stroke-width', cmd.lw || 1.5);
      circle.setAttribute('fill', 'none');
      circle.setAttribute('vector-effect', 'non-scaling-stroke');
      svgOverlay.appendChild(circle);
      return;
    }
  }

  // Flow-based placement fallback
  var r = cmd.r || 30;
  var size = r * 2 + 4;

  var svg = document.createElementNS(svgNS(), 'svg');
  svg.setAttribute('viewBox', '0 0 ' + size + ' ' + size);
  svg.setAttribute('width', Math.min(size, 300));
  svg.setAttribute('height', Math.min(size, 300));
  svg.style.cssText = 'display:block;';

  var circle = document.createElementNS(svgNS(), 'circle');
  circle.setAttribute('cx', r + 2); circle.setAttribute('cy', r + 2);
  circle.setAttribute('r', r);
  circle.setAttribute('stroke', color);
  circle.setAttribute('stroke-width', cmd.lw || 1.5);
  circle.setAttribute('fill', 'none');
  svg.appendChild(circle);

  var el = createElement('div', cmd, 'bd-svg-shape');
  el.appendChild(svg);
  placeElement(el, cmd.placement || 'below', cmd);
}

function renderSvgDot(cmd) {
  var r = cmd.r || 4;
  var color = resolveColor(cmd.color);
  var size = r * 2 + 4;

  var svg = document.createElementNS(svgNS(), 'svg');
  svg.setAttribute('viewBox', '0 0 ' + size + ' ' + size);
  svg.setAttribute('width', size);
  svg.setAttribute('height', size);
  svg.style.cssText = 'display:inline-block;vertical-align:middle;';

  var circle = document.createElementNS(svgNS(), 'circle');
  circle.setAttribute('cx', r + 2); circle.setAttribute('cy', r + 2);
  circle.setAttribute('r', r);
  circle.setAttribute('fill', color);
  svg.appendChild(circle);

  var el = createElement('div', cmd, 'bd-svg-shape');
  el.style.display = 'inline-block';
  el.appendChild(svg);
  placeElement(el, cmd.placement || 'below', cmd);
}

// ── MERMAID: diagrams rendered via Mermaid.js ──
var _mermaidReady = false;
var _mermaidLoading = false;
var _mermaidQueue = [];

function _loadMermaid(cb) {
  if (_mermaidReady) { cb(); return; }
  _mermaidQueue.push(cb);
  if (_mermaidLoading) return;
  _mermaidLoading = true;
  var script = document.createElement('script');
  script.src = 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js';
  script.onload = function() {
    window.mermaid.initialize({
      startOnLoad: false,
      theme: 'dark',
      themeVariables: {
        primaryColor: '#1a2332',
        primaryTextColor: '#e8e8e0',
        primaryBorderColor: '#53d8fb',
        lineColor: '#94a3b8',
        secondaryColor: '#1a2332',
        tertiaryColor: '#1a2332',
        fontFamily: "'CoalhandLuke', 'Caveat', cursive",
        fontSize: '16px',
        nodeBorder: '#53d8fb',
        clusterBkg: 'rgba(52,211,153,0.08)',
        clusterBorder: '#34d399',
        edgeLabelBackground: '#1a1d2e',
        noteTextColor: '#e8e8e0',
        noteBkgColor: '#1a2332',
        noteBorderColor: '#fbbf24',
      }
    });
    _mermaidReady = true;
    _mermaidQueue.forEach(function(fn) { fn(); });
    _mermaidQueue = [];
  };
  script.onerror = function() {
    console.warn('[Mermaid] Failed to load library');
    _mermaidLoading = false;
  };
  document.head.appendChild(script);
}

async function renderMermaid(cmd) {
  if (!cmd.code) return;

  var el = createElement('div', cmd, 'bd-mermaid');
  if (cmd.title) {
    var title = document.createElement('div');
    title.className = 'bd-mermaid-title bd-chalk-cyan bd-size-small';
    title.textContent = cmd.title;
    el.appendChild(title);
  }
  var container = document.createElement('div');
  container.className = 'bd-mermaid-container';
  container.textContent = 'Loading diagram...';
  container.style.cssText = 'color:rgba(52,211,153,0.4);font-size:13px;font-family:monospace;padding:20px;text-align:center;';
  el.appendChild(container);

  placeElement(el, cmd.placement, cmd);

  _loadMermaid(function() {
    try {
      var mermaidId = 'mermaid-' + (cmd.id || Math.random().toString(36).slice(2));
      window.mermaid.render(mermaidId, cmd.code).then(function(result) {
        container.innerHTML = result.svg;
        container.style.cssText = 'padding:8px;';
        // Style the SVG to match the board
        var svg = container.querySelector('svg');
        if (svg) {
          svg.style.maxWidth = '100%';
          svg.style.height = 'auto';
        }
      }).catch(function(err) {
        container.textContent = 'Diagram error: ' + err.message;
        container.style.color = 'rgba(248,113,113,0.5)';
      });
    } catch (err) {
      container.textContent = 'Diagram error: ' + err.message;
      container.style.color = 'rgba(248,113,113,0.5)';
    }
  });
}

// ── CONNECT: draw an SVG arrow between two elements ──
function renderConnect(cmd) {
  if (!cmd.from || !cmd.to) return;

  // Defer rendering to ensure layout is settled
  requestAnimationFrame(function() { _drawConnect(cmd); });
}

function _drawConnect(cmd) {
  var fromEntry = board.elements.get(cmd.from);
  var toEntry = board.elements.get(cmd.to);
  if (!fromEntry || !toEntry) return; // silently skip if elements not found
  var fromEl = fromEntry.element;
  var toEl = toEntry.element;
  if (!fromEl || !toEl || !fromEl.isConnected || !toEl.isConnected) return;

  var scene = board.liveScene;
  if (!scene) return;
  var sceneRect = scene.getBoundingClientRect();
  var fromRect = fromEl.getBoundingClientRect();
  var toRect = toEl.getBoundingClientRect();

  // Skip if elements have no size yet (not rendered)
  if (fromRect.width === 0 || toRect.width === 0) return;

  // Find NEAREST EDGES to connect — not fixed center-bottom/center-top
  var fromCX = fromRect.left + fromRect.width / 2 - sceneRect.left;
  var fromCY = fromRect.top + fromRect.height / 2 - sceneRect.top;
  var toCX = toRect.left + toRect.width / 2 - sceneRect.left;
  var toCY = toRect.top + toRect.height / 2 - sceneRect.top;

  var dx = toCX - fromCX;
  var dy = toCY - fromCY;
  var x1, y1, x2, y2;

  if (Math.abs(dx) > Math.abs(dy)) {
    // Horizontal connection — use right/left edges
    if (dx > 0) {
      x1 = fromRect.right - sceneRect.left + 4;
      x2 = toRect.left - sceneRect.left - 4;
    } else {
      x1 = fromRect.left - sceneRect.left - 4;
      x2 = toRect.right - sceneRect.left + 4;
    }
    y1 = fromCY;
    y2 = toCY;
  } else {
    // Vertical connection — use bottom/top edges
    if (dy > 0) {
      y1 = fromRect.bottom - sceneRect.top + 4;
      y2 = toRect.top - sceneRect.top - 4;
    } else {
      y1 = fromRect.top - sceneRect.top - 4;
      y2 = toRect.bottom - sceneRect.top + 4;
    }
    x1 = fromCX;
    x2 = toCX;
  }

  var color = resolveColor(cmd.color || 'dim');

  // Create or reuse SVG overlay
  var svg = scene.querySelector('.bd-connect-svg');
  if (!svg) {
    svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'bd-connect-svg');
    svg.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;overflow:visible;z-index:5;';
    // Arrowhead defs
    var defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    var marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
    marker.setAttribute('id', 'bd-arrow');
    marker.setAttribute('viewBox', '0 0 10 10');
    marker.setAttribute('refX', '10'); marker.setAttribute('refY', '5');
    marker.setAttribute('markerWidth', '8'); marker.setAttribute('markerHeight', '8');
    marker.setAttribute('orient', 'auto-start-reverse');
    var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', 'M 0 0 L 10 5 L 0 10 z');
    path.setAttribute('fill', 'currentColor');
    marker.appendChild(path);
    defs.appendChild(marker);
    svg.appendChild(defs);
    scene.appendChild(svg);
  }

  // Draw the connection line
  var line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  line.setAttribute('x1', x1); line.setAttribute('y1', y1);
  line.setAttribute('x2', x2); line.setAttribute('y2', y2);
  line.setAttribute('stroke', color);
  line.setAttribute('stroke-width', '1.5');
  line.setAttribute('stroke-dasharray', cmd.dashed ? '6 4' : 'none');
  line.setAttribute('marker-end', 'url(#bd-arrow)');
  line.style.color = color;
  svg.appendChild(line);

  // Optional label on the arrow
  if (cmd.label) {
    var midX = (x1 + x2) / 2;
    var midY = (y1 + y2) / 2;
    var text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', midX); text.setAttribute('y', midY - 6);
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('class', 'bd-connect-label');
    text.setAttribute('fill', color);
    text.textContent = cmd.label;
    svg.appendChild(text);
  }

  if (cmd.id) registerElement(cmd.id, line);
}

// ── DIAGRAM: flowchart/architecture from boxes + arrows ──
async function renderDiagram(cmd) {
  var el = createElement('div', cmd, 'bd-diagram');
  var nodes = cmd.nodes || [];
  var edges = cmd.edges || [];

  // Create a flex container for the diagram boxes
  var container = document.createElement('div');
  container.className = 'bd-diagram-nodes';
  container.style.cssText = 'display:flex;flex-wrap:wrap;gap:16px;align-items:center;justify-content:center;padding:20px;position:relative;';

  var nodeEls = {};
  for (var i = 0; i < nodes.length; i++) {
    var node = nodes[i];
    var box = document.createElement('div');
    box.className = 'bd-diagram-node';
    box.id = node.id || ('dnode-' + i);
    box.style.cssText = 'border:1.5px solid ' + resolveColor(node.color || 'cyan') + ';border-radius:8px;padding:10px 16px;text-align:center;min-width:80px;background:rgba(0,0,0,0.3);';
    var label = document.createElement('div');
    label.className = 'bd-chalk-' + (colorClass(node.color).replace('bd-chalk-','')) + ' bd-size-text';
    label.style.cssText = 'font-family:var(--bd-font);text-shadow:var(--bd-glow);';
    box.appendChild(label);
    container.appendChild(box);
    nodeEls[box.id] = { el: box, text: node.text || node.label || '' };
    if (node.id) registerElement(node.id, box);
  }

  el.appendChild(container);
  placeElement(el, cmd.placement, cmd);

  // Animate node text
  for (var id in nodeEls) {
    if (board.cancelFlag) break;
    await animateText(nodeEls[id].el.querySelector('div'), nodeEls[id].text, { charDelay: 20 });
  }

  // Draw edge arrows (after layout so positions are known)
  if (edges.length > 0) {
    requestAnimationFrame(function() {
      for (var i = 0; i < edges.length; i++) {
        var edge = edges[i];
        renderConnect({ from: edge.from, to: edge.to, label: edge.label, color: edge.color || 'dim' });
      }
    });
  }
}

async function renderText(cmd) {
  var el = createStyledElement('div', cmd, 'bd-text');
  placeElement(el, cmd.placement, cmd);
  await animateText(el, cmd.text, { charDelay: cmd.charDelay });
}

async function renderEquation(cmd) {
  var el = createElement('div', cmd, 'bd-equation');
  el.classList.add(colorClass(cmd.color));

  var main = document.createElement('span');
  main.className = 'bd-eq-main ' + sizeClass(cmd.size);
  el.appendChild(main);

  if (cmd.note) {
    var note = document.createElement('span');
    note.className = 'bd-eq-note bd-chalk-dim ' + sizeClass('small');
    note.textContent = cmd.note;
    el.appendChild(note);
  }

  placeElement(el, cmd.placement, cmd);

  // Try KaTeX rendering for LaTeX expressions, fall back to text animation
  var text = cmd.text || '';
  var rendered = false;

  if (typeof katex !== 'undefined') {
    // Strip surrounding $ or $$ if present
    var latex = text;
    if (latex.startsWith('$$') && latex.endsWith('$$')) {
      latex = latex.slice(2, -2);
    } else if (latex.startsWith('$') && latex.endsWith('$')) {
      latex = latex.slice(1, -1);
    }

    // Convert common Unicode math symbols to LaTeX
    latex = latex
      .replace(/ℏ/g, '\\hbar').replace(/ψ/g, '\\psi').replace(/φ/g, '\\phi')
      .replace(/Ψ/g, '\\Psi').replace(/Φ/g, '\\Phi')
      .replace(/∂/g, '\\partial').replace(/∇/g, '\\nabla')
      .replace(/α/g, '\\alpha').replace(/β/g, '\\beta').replace(/γ/g, '\\gamma')
      .replace(/δ/g, '\\delta').replace(/ε/g, '\\epsilon').replace(/θ/g, '\\theta')
      .replace(/λ/g, '\\lambda').replace(/σ/g, '\\sigma').replace(/ω/g, '\\omega')
      .replace(/π/g, '\\pi').replace(/μ/g, '\\mu').replace(/τ/g, '\\tau')
      .replace(/Ω/g, '\\Omega').replace(/Σ/g, '\\Sigma').replace(/Δ/g, '\\Delta')
      .replace(/∫/g, '\\int').replace(/∑/g, '\\sum').replace(/∞/g, '\\infty')
      .replace(/≈/g, '\\approx').replace(/≠/g, '\\neq').replace(/≤/g, '\\leq').replace(/≥/g, '\\geq')
      .replace(/→/g, '\\rightarrow').replace(/←/g, '\\leftarrow')
      .replace(/·/g, '\\cdot').replace(/×/g, '\\times').replace(/±/g, '\\pm')
      .replace(/²/g, '^{2}').replace(/³/g, '^{3}').replace(/₀/g, '_{0}')
      .replace(/₁/g, '_{1}').replace(/₂/g, '_{2}').replace(/₃/g, '_{3}')
      .replace(/ₙ/g, '_{n}').replace(/ₓ/g, '_{x}').replace(/ᵢ/g, '_{i}');

    // Detect if this looks like LaTeX (has commands or math operators)
    var hasLatex = /[\\{}^_]|\\frac|\\partial|\\sum|\\int|\\hbar|\\psi|\\phi|\\nabla|\\vec|\\hat|\\dot|\\sqrt|\\infty|\\alpha|\\beta|\\gamma|\\delta|\\epsilon|\\theta|\\lambda|\\sigma|\\omega|\\cdot|\\times|\\approx|\\neq|\\leq|\\geq|\\rightarrow/.test(latex);

    if (hasLatex) {
      try {
        main.innerHTML = katex.renderToString(latex, {
          displayMode: false,
          throwOnError: false,
          trust: true,
        });
        rendered = true;
      } catch (e) {
        // KaTeX failed — fall back to text
      }
    }
  }

  if (!rendered) {
    await animateText(main, text, { charDelay: cmd.charDelay });
  }
}

async function renderCompare(cmd) {
  var el = createElement('div', cmd, 'bd-compare');
  var left = cmd.left || {};
  var right = cmd.right || {};

  var leftCol = document.createElement('div');
  leftCol.className = 'bd-compare-col ' + colorClass(left.color);

  var sep = document.createElement('div');
  sep.className = 'bd-compare-sep';

  var rightCol = document.createElement('div');
  rightCol.className = 'bd-compare-col ' + colorClass(right.color);

  el.appendChild(leftCol);
  el.appendChild(sep);
  el.appendChild(rightCol);

  placeElement(el, cmd.placement, cmd);

  // Animate titles first, then items one-by-one, alternating left/right
  if (left.title) {
    var h = document.createElement('div');
    h.className = 'bd-compare-col-label ' + sizeClass('h2');
    leftCol.appendChild(h);
    await animateText(h, left.title);
  }
  if (right.title) {
    var h = document.createElement('div');
    h.className = 'bd-compare-col-label ' + sizeClass('h2');
    rightCol.appendChild(h);
    await animateText(h, right.title);
  }

  // Animate items alternating left/right for natural feel
  var leftItems = left.items || [];
  var rightItems = right.items || [];
  var maxLen = Math.max(leftItems.length, rightItems.length);

  for (var i = 0; i < maxLen; i++) {
    if (i < leftItems.length) {
      var li = document.createElement('div');
      li.className = 'bd-compare-item ' + sizeClass('text');
      leftCol.appendChild(li);
      await animateText(li, '\u2022 ' + leftItems[i]);
    }
    if (i < rightItems.length) {
      var li = document.createElement('div');
      li.className = 'bd-compare-item ' + sizeClass('text');
      rightCol.appendChild(li);
      await animateText(li, '\u2022 ' + rightItems[i]);
    }
  }
}

async function renderStep(cmd) {
  var el = createElement('div', cmd, 'bd-step', colorClass(cmd.color || 'cyan'));

  var num = document.createElement('span');
  num.className = 'bd-step-num';
  num.textContent = String(cmd.n || 1);
  el.appendChild(num);

  var text = document.createElement('span');
  text.className = 'bd-step-text ' + sizeClass(cmd.size);
  el.appendChild(text);

  placeElement(el, cmd.placement, cmd);
  await animateText(text, cmd.text, { charDelay: cmd.charDelay });
}

async function renderCheckCross(cmd, isCheck) {
  var el = createElement('div', cmd, isCheck ? 'bd-check' : 'bd-cross');

  var text = document.createElement('span');
  text.className = 'bd-check-text ' + colorClass(cmd.color || 'white') + ' ' + sizeClass(cmd.size);
  el.appendChild(text);

  placeElement(el, cmd.placement, cmd);
  await animateText(text, cmd.text, { charDelay: cmd.charDelay || 25 });
}

async function renderCallout(cmd) {
  var el = createElement('div', cmd, 'bd-callout', colorClass(cmd.color || 'gold'));

  var text = document.createElement('div');
  text.className = 'bd-callout-text ' + sizeClass(cmd.size);
  el.appendChild(text);

  placeElement(el, cmd.placement, cmd);
  await animateText(text, cmd.text, { charDelay: cmd.charDelay });
}

async function renderList(cmd) {
  var el = createElement('div', cmd, 'bd-list', colorClass(cmd.color || 'white'));
  el.dataset.style = cmd.style || 'bullet';

  var items = cmd.items || [];
  for (var item of items) {
    var li = document.createElement('div');
    li.className = 'bd-list-item ' + sizeClass(cmd.size);
    el.appendChild(li);
  }

  placeElement(el, cmd.placement, cmd);

  var listItems = el.querySelectorAll('.bd-list-item');
  for (var i = 0; i < items.length && i < listItems.length; i++) {
    if (board.cancelFlag) break;
    await animateText(listItems[i], items[i], { charDelay: 25 });
  }
}

function renderDivider(cmd) {
  var el = document.createElement('hr');
  el.className = 'bd-el bd-divider';
  if (cmd.id) el.id = cmd.id;
  placeElement(el, cmd.placement, cmd);
}

async function renderResult(cmd) {
  var el = createElement('div', cmd, 'bd-result', colorClass(cmd.color || 'gold'));

  if (cmd.label) {
    var label = document.createElement('span');
    label.className = 'bd-result-label';
    label.textContent = cmd.label;
    el.appendChild(label);
  }

  var text = document.createElement('span');
  text.className = 'bd-result-text ' + sizeClass(cmd.size);
  el.appendChild(text);

  if (cmd.note) {
    var note = document.createElement('span');
    note.className = 'bd-result-note bd-chalk-dim ' + sizeClass('small');
    note.textContent = '\u2190 ' + cmd.note;
    el.appendChild(note);
  }

  placeElement(el, cmd.placement, cmd);
  await animateText(text, cmd.text, { charDelay: cmd.charDelay });
}

function renderStrikeout(cmd) {
  if (!cmd.target) return;
  var el = document.getElementById(cmd.target);
  if (el) el.classList.add('bd-strikeout');
}

async function renderUpdate(cmd) {
  if (!cmd.target || !cmd.text) return;
  var el = document.getElementById(cmd.target);
  if (!el) return;
  el.textContent = '';
  if (cmd.color) {
    el.className = el.className.replace(/bd-chalk-\w+/g, '');
    el.classList.add(colorClass(cmd.color));
  }
  await animateText(el, cmd.text, { charDelay: 20 });
}

function renderDelete(cmd) {
  if (!cmd.target) return;
  var el = document.getElementById(cmd.target);
  if (el) el.classList.add('bd-deleted');
}

async function renderClone(cmd) {
  if (!cmd.source) return;
  var source = document.getElementById(cmd.source);
  if (!source) return;
  var clone = source.cloneNode(true);
  clone.id = cmd.id || (cmd.source + '-copy');
  clone.classList.remove('bd-strikeout', 'bd-deleted', 'bd-highlight');
  placeElement(clone, cmd.placement || 'below', cmd);
}

function autoScroll() {
  var wrap = document.getElementById('bd-canvas-wrap');
  if (!wrap || !board.liveScene) return;

  // If user manually scrolled up, don't force them down.
  // But auto-resume if they've been idle for 3+ seconds (they stopped browsing).
  if (board._userScrolledUp) {
    var now = Date.now();
    if (board._lastUserScrollTime && now - board._lastUserScrollTime > 3000) {
      board._userScrolledUp = false; // Auto-resume after idle
    } else {
      return;
    }
  }

  var allEls = board.liveScene.querySelectorAll('.bd-el, .bd-anim-figure, .bd-svg-shape, .bd-row, .bd-zone-grid, .bd-columns, .bd-positioned');
  if (!allEls.length) return;
  var lastEl = allEls[allEls.length - 1];

  requestAnimationFrame(function() {
    var wrapRect = wrap.getBoundingClientRect();
    var elRect = lastEl.getBoundingClientRect();

    // Scroll if new content is below the top 70% of viewport
    // This keeps new content appearing near the top, not accumulating at the bottom
    if (elRect.top > wrapRect.top + wrapRect.height * 0.6 || elRect.bottom > wrapRect.bottom - 40) {
      // Place the new element near the top (20% from top of viewport)
      var targetTop = wrap.scrollTop + (elRect.top - wrapRect.top) - wrapRect.height * 0.2;
      wrap.scrollTo({ top: Math.max(0, targetTop), behavior: 'smooth' });
    }
  });
}

// ═══════════════════════════════════════════════════════════════
// 9. INDEX — Public API + init/zoom
// ═══════════════════════════════════════════════════════════════

function init(apiUrl, authHeadersFn) {
  board.apiUrl = apiUrl || window.location.origin || '';
  board.getAuthHeaders = authHeadersFn || function() {
    // Try to use AuthManager if available on window
    if (typeof AuthManager !== 'undefined' && AuthManager.authHeaders) {
      return AuthManager.authHeaders();
    }
    return {};
  };
  board.cancelFlag = false;

  var liveScene = document.getElementById('bd-live-scene');
  if (!liveScene) {
    var boardContent = document.getElementById('bd-board-content');
    if (boardContent) {
      liveScene = document.createElement('div');
      liveScene.id = 'bd-live-scene';
      liveScene.className = 'bd-scene';
      liveScene.innerHTML = '<div class="bd-grid-bg"></div>';
      boardContent.appendChild(liveScene);
    }
  }
  board.liveScene = liveScene;
  board.currentRow = null;

  initZoom();

  var wrap = document.getElementById('bd-canvas-wrap');
  if (wrap && !wrap._bdScrollInit) {
    wrap._bdScrollInit = true;
    var scrollTimer;
    var lastScrollTop = wrap.scrollTop;
    wrap.addEventListener('scroll', function() {
      var currentTop = wrap.scrollTop;
      var maxScroll = wrap.scrollHeight - wrap.clientHeight;
      if (currentTop < lastScrollTop - 30) {
        // User scrolled up — pause auto-scroll temporarily
        board._userScrolledUp = true;
        board._lastUserScrollTime = Date.now();
      }
      if (currentTop >= maxScroll - 60) {
        // User scrolled to bottom — resume immediately
        board._userScrolledUp = false;
      }
      lastScrollTop = currentTop;

      if (scrollTimer) clearTimeout(scrollTimer);
      scrollTimer = setTimeout(function() { updateAnimationVisibility(); }, 200);
    }, { passive: true });
  }

  if (board.commandQueue.length > 0 && !board.isProcessing) {
    processQueue();
  }
}

function queueCommand(cmd) {
  board.commandQueue.push(cmd);
  if (!board.isProcessing) processQueue();
}

async function processQueue() {
  if (board.isProcessing) return;
  board.isProcessing = true;

  while (board.commandQueue.length > 0) {
    if (board.cancelFlag) {
      board.commandQueue = [];
      break;
    }
    var cmd = board.commandQueue.shift();
    try {
      await runCommand(cmd);
    } catch (e) {
      console.error('[Board] Command error:', e.message, cmd);
    }
  }

  board.isProcessing = false;
}

function cancel() {
  board.cancelFlag = true;
  board.commandQueue = [];
  board.isProcessing = false;
}

function cleanup() {
  cancel();
  resetState();
}

function initZoom() {
  var wrap = document.getElementById('bd-canvas-wrap');
  if (!wrap || wrap._bdZoomInit) return;
  wrap._bdZoomInit = true;

  function applyZoom() {
    var z = board.zoom;
    var content = document.getElementById('bd-board-content');
    if (content) {
      content.style.transformOrigin = 'top left';
      content.style.transform = z === 1 ? '' : 'scale(' + z + ')';
    }
    var label = document.getElementById('bd-zoom-level');
    if (label) label.textContent = Math.round(z * 100) + '%';
  }

  wrap.addEventListener('wheel', function(e) {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      var oldZ = board.zoom;
      board.zoom = Math.max(0.4, Math.min(4, oldZ * (1 - e.deltaY * 0.003)));
      applyZoom();
    }
  }, { passive: false });

  var lastPinchDist = 0;
  wrap.addEventListener('touchstart', function(e) {
    if (e.touches.length === 2) {
      lastPinchDist = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
    }
  }, { passive: true });
  wrap.addEventListener('touchmove', function(e) {
    if (e.touches.length === 2 && lastPinchDist > 0) {
      var dist = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
      board.zoom = Math.max(0.4, Math.min(4, board.zoom * dist / lastPinchDist));
      lastPinchDist = dist;
      applyZoom();
    }
  }, { passive: true });
  wrap.addEventListener('touchend', function() { lastPinchDist = 0; }, { passive: true });

  window.bdZoomIn = function() { board.zoom = Math.min(4, board.zoom * 1.25); applyZoom(); };
  window.bdZoomOut = function() { board.zoom = Math.max(0.4, board.zoom / 1.25); applyZoom(); };
  window.bdZoomReset = function() { board.zoom = 1.15; applyZoom(); };

  document.addEventListener('keydown', function(e) {
    if (!board.liveScene) return;
    if ((e.ctrlKey || e.metaKey) && (e.key === '=' || e.key === '+')) { e.preventDefault(); window.bdZoomIn(); }
    else if ((e.ctrlKey || e.metaKey) && e.key === '-') { e.preventDefault(); window.bdZoomOut(); }
    else if ((e.ctrlKey || e.metaKey) && e.key === '0') { e.preventDefault(); window.bdZoomReset(); }
  });
}

// ── Public API ──

var Board = {
  init: init,
  queueCommand: queueCommand,
  processQueue: processQueue,
  cancel: cancel,
  cleanup: cleanup,
  snapshotScene: snapshotScene,
  clearAll: clearAll,
  zoomPulse: zoomPulse,
  scrollToElement: scrollToElement,
  get state() { return board; },
};

window.BoardEngine = Board;

})();
