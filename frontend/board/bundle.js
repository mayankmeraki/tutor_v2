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
  cancelFlag: false,
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
  board.cancelFlag = false;
  board.commandQueue = [];
  board.isProcessing = false;
  board.elements.clear();
  board.scenes = [];
  board.animations.forEach(a => { try { a.instance.remove(); } catch(e) {} });
  board.animations = [];
  board.zoom = 1;
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
  var instant = options.instant || queueLen > 5 || animCount > 4;
  var delay = options.charDelay;
  if (delay === undefined) {
    delay = animCount > 2 ? 15 : animCount > 0 ? 25 : 35;
  }

  if (instant || delay === 0) {
    parentEl.textContent = text;
    return;
  }

  var fragment = document.createDocumentFragment();
  var chars = [];
  for (var ch of text) {
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

  parentEl.textContent = text;
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

  if (placement === 'right') {
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

  return code;
}

function buildControlBridge(scale, isWebGL) {
  return '\n' +
    '    var _controlParams = {};\n' +
    '    var S = ' + scale.toFixed(2) + ';\n' +
    '    function onControl(params) {\n' +
    '      if (params._unhighlight) { _controlParams._highlight = null; }\n' +
    '      Object.assign(_controlParams, params);\n' +
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
    '      if (!p[m] && p.drawingContext && typeof p.drawingContext[m] === \'function\') {\n' +
    '        p[m] = function() { return p.drawingContext[m].apply(p.drawingContext, arguments); };\n' +
    '      }\n' +
    '    });\n' +
    (isWebGL ? '\n    p.text = function() {};\n    p.textFont = function() {};\n    p.textSize = function() {};\n    p.textAlign = function() {};\n' : '') +
    '  ';
}

function createAnimation(cmd) {
  if (!cmd.code) return;

  // If animation has a legend property, wrap in a row with legend sidebar
  var wrapper = null;
  if (cmd.legend && Array.isArray(cmd.legend) && cmd.legend.length > 0) {
    wrapper = document.createElement('div');
    wrapper.className = 'bd-row';
    if (cmd.id) wrapper.id = cmd.id + '-wrap';
  }

  var el = createElement('div', { id: cmd.id, cmd: cmd.cmd }, 'bd-anim-box');

  var controls = document.createElement('div');
  controls.className = 'bd-anim-controls';
  var expandBtn = document.createElement('button');
  expandBtn.className = 'bd-anim-expand-btn';
  expandBtn.textContent = '\u26F6';
  expandBtn.title = 'Expand animation';
  expandBtn.addEventListener('click', function() {
    // TODO: fullscreen modal
  });
  controls.appendChild(expandBtn);
  el.appendChild(controls);

  var canvasWrap = document.createElement('div');
  canvasWrap.className = 'bd-anim-canvas-wrap';
  canvasWrap.style.cssText = 'width:100%;height:100%;overflow:hidden;border-radius:4px;';
  el.appendChild(canvasWrap);

  // Set explicit dimensions BEFORE placing in DOM — prevents 0-height collapse
  var animH = cmd.h || 280;
  var animW = cmd.w || 420;
  el.style.minHeight = animH + 'px';
  el.style.aspectRatio = (animW / animH).toFixed(3);

  // Place: if has legend, use wrapper row; otherwise place directly
  if (wrapper) {
    wrapper.appendChild(el);

    // Build legend column
    var legendCol = document.createElement('div');
    legendCol.className = 'bd-column bd-anim-legend';
    var legendTitle = document.createElement('div');
    legendTitle.className = 'bd-el bd-chalk-gold bd-size-h3';
    legendTitle.textContent = 'Legend:';
    legendTitle.style.marginTop = '0';
    legendCol.appendChild(legendTitle);

    cmd.legend.forEach(function(item) {
      var li = document.createElement('div');
      li.className = 'bd-el bd-size-small ' + colorClass(item.color);
      li.textContent = item.text || item;
      li.style.marginTop = '4px';
      legendCol.appendChild(li);
    });

    wrapper.appendChild(legendCol);
    placeElement(wrapper, cmd.placement, cmd);
  } else {
    placeElement(el, cmd.placement, cmd);
  }

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
      console.warn('[Animation] Compile error — calling Haiku fix:', e.message);
      showSkeleton(el, canvasWrap, cmd, e.message, scale, isWebGL);
      return;
    }
  }

  var inst;
  try {
    inst = new p5(function(p) {
      try { sketchFn(p, pw, ph); } catch (err) {
        console.error('[Animation] Sketch error:', err.message);
        canvasWrap.innerHTML = '<div style="padding:12px;color:rgba(248,113,113,0.4);font-size:12px;font-family:monospace">Animation error</div>';
        return;
      }
      var userDraw = p.draw;
      if (userDraw) {
        var errors = 0;
        p.draw = function () {
          try { userDraw.call(p); } catch (err) {
            if (++errors === 1) console.warn('[Animation] draw() error:', err.message);
            if (errors >= 60) p.noLoop();
          }
        };
      }
      var userSetup = p.setup;
      p.setup = function () {
        if (userSetup) userSetup.call(p);
        try { if (!p._renderer.isP3D) p.textFont('Caveat'); } catch (e) {}
      };
    }, canvasWrap);
  } catch (e) {
    canvasWrap.innerHTML = '<div style="padding:12px;color:rgba(248,113,113,0.4);font-size:12px">Init error</div>';
    return;
  }

  el._p5Instance = inst;
  var entry = { container: el, instance: inst, _running: true };
  board.animations.push(entry);

  var retryKey = cmd.id || 'anon';
  var attempt = board.animRetries.get(retryKey) || 0;
  if (attempt < 1) {
    setTimeout(function() { detectBlank(canvasWrap, entry, cmd, retryKey, attempt); }, 2500);
  }
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
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: cmd.code, error: 'Canvas all black. Fix drawing logic.' }),
    })
      .then(function(r) { return r.ok ? r.json() : null; })
      .then(function(data) {
        if (!data || !data.code) throw new Error('No code');
        try { entry.instance.remove(); } catch (e) {}
        if (entry.container && entry.container.parentNode) entry.container.parentNode.removeChild(entry.container);
        var idx = board.animations.indexOf(entry);
        if (idx >= 0) board.animations.splice(idx, 1);
        createAnimation(Object.assign({}, cmd, { code: data.code }));
      })
      .catch(function() {
        try { entry.instance.remove(); } catch (e) {}
        if (entry.container && entry.container.parentNode) entry.container.parentNode.removeChild(entry.container);
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
    headers: { 'Content-Type': 'application/json' },
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
        p.setup = function () { if (userSetup) userSetup.call(p); };
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
  if (!board.liveScene) return;

  var contentCmds = ['text', 'latex', 'animation', 'equation', 'compare', 'step',
    'check', 'cross', 'callout', 'list', 'divider', 'result',
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
    case 'list':     await renderList(cmd); break;
    case 'divider':  renderDivider(cmd); break;
    case 'result':   await renderResult(cmd); break;
    case 'animation': await createAnimation(cmd); break;
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
    default:
      console.warn('[Board] Unknown command:', cmd.cmd);
  }

  autoScroll();
}

// ── SVG Shape Primitives ──

function svgNS() { return 'http://www.w3.org/2000/svg'; }

function resolveColor(c) {
  var map = { white:'#e8e8e0', yellow:'#f5d97a', gold:'#fbbf24', green:'#34d399',
    blue:'#7eb8da', red:'#ff6b6b', cyan:'#53d8fb', dim:'#94a3b8' };
  return map[c] || c || '#e8e8e0';
}

function renderSvgLine(cmd) {
  var x1 = cmd.x1 || 0, y1 = cmd.y1 || 0, x2 = cmd.x2 || 100, y2 = cmd.y2 || 0;
  var w = Math.abs(x2 - x1) || 10, h = Math.abs(y2 - y1) || 10;
  var pad = 10;
  var svgW = w + pad * 2, svgH = Math.max(h + pad * 2, 20);
  var minX = Math.min(x1, x2), minY = Math.min(y1, y2);

  var svg = document.createElementNS(svgNS(), 'svg');
  svg.setAttribute('viewBox', '0 0 ' + svgW + ' ' + svgH);
  svg.setAttribute('width', Math.min(svgW, 600));
  svg.setAttribute('height', Math.min(svgH, 200));
  svg.style.cssText = 'display:block;overflow:visible;';

  var line = document.createElementNS(svgNS(), 'line');
  line.setAttribute('x1', x1 - minX + pad);
  line.setAttribute('y1', y1 - minY + pad);
  line.setAttribute('x2', x2 - minX + pad);
  line.setAttribute('y2', y2 - minY + pad);
  line.setAttribute('stroke', resolveColor(cmd.color));
  line.setAttribute('stroke-width', cmd.w || 2);
  if (cmd.cmd === 'dashed') line.setAttribute('stroke-dasharray', '8 4');
  line.setAttribute('stroke-linecap', 'round');
  svg.appendChild(line);

  var el = createElement('div', cmd, 'bd-svg-shape');
  el.appendChild(svg);
  placeElement(el, cmd.placement || 'below', cmd);
}

function renderSvgArrow(cmd) {
  var x1 = cmd.x1 || 0, y1 = cmd.y1 || 0, x2 = cmd.x2 || 100, y2 = cmd.y2 || 0;
  var w = Math.abs(x2 - x1) || 10, h = Math.abs(y2 - y1) || 10;
  var pad = 15;
  var svgW = w + pad * 2, svgH = Math.max(h + pad * 2, 20);
  var minX = Math.min(x1, x2), minY = Math.min(y1, y2);
  var color = resolveColor(cmd.color);

  var svg = document.createElementNS(svgNS(), 'svg');
  svg.setAttribute('viewBox', '0 0 ' + svgW + ' ' + svgH);
  svg.setAttribute('width', Math.min(svgW, 600));
  svg.setAttribute('height', Math.min(svgH, 200));
  svg.style.cssText = 'display:block;overflow:visible;';

  // Arrowhead marker
  var defs = document.createElementNS(svgNS(), 'defs');
  var marker = document.createElementNS(svgNS(), 'marker');
  marker.setAttribute('id', 'arr-' + (cmd.id || Math.random().toString(36).slice(2)));
  marker.setAttribute('viewBox', '0 0 10 10');
  marker.setAttribute('refX', '10'); marker.setAttribute('refY', '5');
  marker.setAttribute('markerWidth', '8'); marker.setAttribute('markerHeight', '8');
  marker.setAttribute('orient', 'auto-start-reverse');
  var path = document.createElementNS(svgNS(), 'path');
  path.setAttribute('d', 'M 0 0 L 10 5 L 0 10 z');
  path.setAttribute('fill', color);
  marker.appendChild(path);
  defs.appendChild(marker);
  svg.appendChild(defs);

  var line = document.createElementNS(svgNS(), 'line');
  line.setAttribute('x1', x1 - minX + pad);
  line.setAttribute('y1', y1 - minY + pad);
  line.setAttribute('x2', x2 - minX + pad);
  line.setAttribute('y2', y2 - minY + pad);
  line.setAttribute('stroke', color);
  line.setAttribute('stroke-width', cmd.w || 2);
  line.setAttribute('marker-end', 'url(#' + marker.getAttribute('id') + ')');
  svg.appendChild(line);

  var el = createElement('div', cmd, 'bd-svg-shape');
  el.appendChild(svg);
  placeElement(el, cmd.placement || 'below', cmd);
}

function renderSvgRect(cmd) {
  var rw = cmd.w || 100, rh = cmd.h || 60;
  var color = resolveColor(cmd.color);

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
  var r = cmd.r || 30;
  var color = resolveColor(cmd.color);
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
  await animateText(main, cmd.text, { charDelay: cmd.charDelay });
}

async function renderCompare(cmd) {
  var el = createElement('div', cmd, 'bd-compare');
  var left = cmd.left || {};
  var right = cmd.right || {};

  var leftCol = document.createElement('div');
  leftCol.className = 'bd-compare-col ' + colorClass(left.color);
  if (left.title) {
    var h = document.createElement('div');
    h.className = 'bd-compare-col-label ' + sizeClass('h2');
    h.textContent = left.title;
    leftCol.appendChild(h);
  }
  (left.items || []).forEach(function(item) {
    var li = document.createElement('div');
    li.className = 'bd-compare-item ' + sizeClass('text');
    li.textContent = '\u2022 ' + item;
    leftCol.appendChild(li);
  });

  var sep = document.createElement('div');
  sep.className = 'bd-compare-sep';

  var rightCol = document.createElement('div');
  rightCol.className = 'bd-compare-col ' + colorClass(right.color);
  if (right.title) {
    var h = document.createElement('div');
    h.className = 'bd-compare-col-label ' + sizeClass('h2');
    h.textContent = right.title;
    rightCol.appendChild(h);
  }
  (right.items || []).forEach(function(item) {
    var li = document.createElement('div');
    li.className = 'bd-compare-item ' + sizeClass('text');
    li.textContent = '\u2022 ' + item;
    rightCol.appendChild(li);
  });

  el.appendChild(leftCol);
  el.appendChild(sep);
  el.appendChild(rightCol);

  placeElement(el, cmd.placement, cmd);
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

  var lastEl = board.liveScene.lastElementChild;
  if (!lastEl || lastEl.classList.contains('bd-grid-bg')) return;

  var wrapRect = wrap.getBoundingClientRect();
  var elRect = lastEl.getBoundingClientRect();

  if (elRect.bottom > wrapRect.bottom - 20) {
    lastEl.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }
}

// ═══════════════════════════════════════════════════════════════
// 9. INDEX — Public API + init/zoom
// ═══════════════════════════════════════════════════════════════

function init(apiUrl) {
  board.apiUrl = apiUrl || '';
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
    wrap.addEventListener('scroll', function() {
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
  window.bdZoomReset = function() { board.zoom = 1; applyZoom(); };

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
