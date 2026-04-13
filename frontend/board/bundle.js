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
  // Interactive code runners — populated by renderCode when editable/runnable
  // is set. Each entry tracks current code, last run output, and test results.
  // Shipped to the tutor via buildContext() on the next student MESSAGE.
  codeRunners: {},
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

  // Normalize literal escape sequences from model JSON. The model
  // sometimes emits "\\n" inside `draw='{...}'` attribute strings, which
  // JSON.parse turns into the literal 2 chars `\n` (backslash + n) instead
  // of a real newline byte. Same for \r and \t. Convert them all here so
  // multi-line text always renders as line breaks regardless of how the
  // model escaped its output.
  if (typeof text === 'string' && text.indexOf('\\') !== -1) {
    text = text
      .replace(/\\n/g, '\n')
      .replace(/\\r/g, '\r')
      .replace(/\\t/g, '\t');
  }

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

  // ── FIGURE NARRATION ROUTING ──
  // placement="figure:<id>" routes any content into the matching figure's
  // narration column. Lets the model put a mix of headings/text/lists/
  // callouts beside an animation without inventing per-type commands.
  if (typeof placement === 'string' && placement.indexOf('figure:') === 0) {
    var figId = placement.slice('figure:'.length);
    var fig = document.getElementById(figId);
    if (fig && fig.classList.contains('bd-figure')) {
      var narrationCol = fig.querySelector('.bd-figure-narration');
      if (narrationCol) {
        narrationCol.appendChild(element);
        requestAnimationFrame(function() {
          narrationCol.scrollTop = narrationCol.scrollHeight;
        });

        // ── AUTO-SYNC: reveal next animation phase when narration arrives ──
        // Find animation inside this figure and advance its state.
        var animEntry = null;
        for (var ai = 0; ai < board.animations.length; ai++) {
          var candidate = board.animations[ai];
          if (candidate.container && fig.contains(candidate.container)) { animEntry = candidate; break; }
        }
        if (animEntry) {
          var revealed = false;
          // Path 1: p5 + AnimHelper
          var p5inst = animEntry.instance;
          var helper = p5inst && p5inst._animHelper;
          if (helper && helper.state && helper._onControl) {
            var keys = Object.keys(helper.state);
            for (var ki = 0; ki < keys.length; ki++) {
              if (helper.state[keys[ki]] < 0.5) {
                helper._onControl({ action: 'set', param: keys[ki], value: 1 });
                revealed = true;
                break;
              }
            }
          }
          // Path 2: Three.js — reveal next hidden direct child (Group, Object3D, Mesh)
          // with smooth scale-up. Checks any direct scene child, not just Groups.
          if (!revealed && animEntry._threeScene) {
            var children = animEntry._threeScene.children;
            for (var ci = 0; ci < children.length; ci++) {
              var child = children[ci];
              // Skip lights, helpers, and already-visible objects
              if (child.visible) continue;
              if (child.type === 'AmbientLight' || child.type === 'DirectionalLight' ||
                  child.type === 'PointLight' || child.type === 'AxesHelper' ||
                  child.type === 'GridHelper') continue;
              child.visible = true;
              child.scale.setScalar(0);
              child._revealProgress = 0;
              revealed = true;
              break;
            }
          }
        }
        return;
      }
    }
    // Figure not found — fall through to normal below placement so the
    // content still appears somewhere instead of being silently dropped.
    placement = 'below';
  }

  // ── PERCENTAGE-BASED ABSOLUTE POSITIONING ──
  // If cmd has x/y (0-100), position absolutely within the scene.
  // This gives the LLM free spatial control like a real chalkboard.
  if (typeof cmd.x === 'number' && typeof cmd.y === 'number') {
    // ── Free coordinate space for x,y positioned elements ──
    // The canvas is a transparent reference container — no border, no
    // background, no chrome. x,y are 0-100 percentages of this canvas.
    // Aspect ratio is preserved so coordinates land predictably.
    var canvas = scene.querySelector('.bd-draw-canvas');
    if (!canvas) {
      canvas = document.createElement('div');
      canvas.className = 'bd-draw-canvas';
      canvas.style.cssText = 'position:relative;width:100%;max-width:800px;margin:8px auto;' +
        'aspect-ratio:8/5;min-height:400px;';
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
  var strChar = null;  // null = not in string; otherwise the quote char that opened it
  var esc = false;
  var inLineComment = false;
  var inBlockComment = false;
  for (var i = 0; i < code.length; i++) {
    var ch = code[i];
    var next = code[i + 1];
    if (inLineComment) {
      if (ch === '\n') inLineComment = false;
      continue;
    }
    if (inBlockComment) {
      if (ch === '*' && next === '/') { inBlockComment = false; i++; }
      continue;
    }
    if (esc) { esc = false; continue; }
    if (strChar) {
      if (ch === '\\') { esc = true; continue; }
      if (ch === strChar) { strChar = null; }
      continue;
    }
    // Not in string
    if (ch === '/' && next === '/') { inLineComment = true; i++; continue; }
    if (ch === '/' && next === '*') { inBlockComment = true; i++; continue; }
    if (ch === "'" || ch === '"' || ch === '`') { strChar = ch; continue; }
    if (ch === '{') stack.push('}');
    else if (ch === '(') stack.push(')');
    else if (ch === '[') stack.push(']');
    else if (ch === '}' || ch === ')' || ch === ']') stack.pop();
  }
  if (stack.length) code += stack.reverse().join('');

  code = code.replace(/\b(let|const|var)\s+(W|H)\b\s*=/g, '$2 =');
  code = code.replace(/\b(let|const|var)\s+S\b\s*=/g, 'S =');

  // ── GLOBAL-MODE → INSTANCE-MODE CONVERSION ──
  // LLMs often generate p5 "global mode" code: `function setup() { createCanvas(...) }`
  // But we run in instance mode where p5 expects `p.setup = function() { ... };`.
  // Convert top-level function declarations to p5 instance assignments,
  // adding semicolons to prevent `}p.draw` being parsed as `}` then `p` (unexpected identifier).
  code = code.replace(/\bfunction\s+setup\s*\(/g, '; p.setup = function(');
  code = code.replace(/\bfunction\s+draw\s*\(/g, '; p.draw = function(');
  code = code.replace(/\bfunction\s+mousePressed\s*\(/g, '; p.mousePressed = function(');
  code = code.replace(/\bfunction\s+keyPressed\s*\(/g, '; p.keyPressed = function(');
  code = code.replace(/\bfunction\s+windowResized\s*\(/g, '; p.windowResized = function(');
  // Ensure closing brace of each converted function is followed by semicolon
  code = code.replace(/\}(\s*)(p\.(setup|draw|mousePressed|keyPressed|windowResized)\s*=)/g, '};\n$1$2');

  // Replace p.background(...) / background(...) with board bg fill.
  code = code.replace(/\bp\.background\s*\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\)/g, 'p.background(6,14,17)');
  code = code.replace(/(?<![\w.])background\s*\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\)/g, 'p.background(6,14,17)');

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
  // ── LOCAL BINDINGS for global-mode p5 code ──
  // LLMs generate code like `fill(255); text("hi",10,10)` (global mode)
  // but we run in instance mode where those are `p.fill(...)`, `p.text(...)`.
  // Create local variables that proxy to `p` so both styles work.
  var p5Bindings =
    '    var createCanvas=function(){return p.createCanvas.apply(p,arguments)};\n' +
    '    var resizeCanvas=function(){return p.resizeCanvas.apply(p,arguments)};\n' +
    '    var noLoop=function(){return p.noLoop()};\n' +
    '    var loop=function(){return p.loop()};\n' +
    '    var push=function(){return p.push()};\n' +
    '    var pop=function(){return p.pop()};\n' +
    '    var fill=function(){return p.fill.apply(p,arguments)};\n' +
    '    var noFill=function(){return p.noFill()};\n' +
    '    var stroke=function(){return p.stroke.apply(p,arguments)};\n' +
    '    var noStroke=function(){return p.noStroke()};\n' +
    '    var strokeWeight=function(){return p.strokeWeight.apply(p,arguments)};\n' +
    '    var rect=function(){return p.rect.apply(p,arguments)};\n' +
    '    var ellipse=function(){return p.ellipse.apply(p,arguments)};\n' +
    '    var circle=function(){return p.circle.apply(p,arguments)};\n' +
    '    var arc=function(){return p.arc.apply(p,arguments)};\n' +
    '    var line=function(){return p.line.apply(p,arguments)};\n' +
    '    var point=function(){return p.point.apply(p,arguments)};\n' +
    '    var triangle=function(){return p.triangle.apply(p,arguments)};\n' +
    '    var quad=function(){return p.quad.apply(p,arguments)};\n' +
    '    var vertex=function(){return p.vertex.apply(p,arguments)};\n' +
    '    var beginShape=function(){return p.beginShape.apply(p,arguments)};\n' +
    '    var endShape=function(){return p.endShape.apply(p,arguments)};\n' +
    '    var bezierVertex=function(){return p.bezierVertex.apply(p,arguments)};\n' +
    '    var curveVertex=function(){return p.curveVertex.apply(p,arguments)};\n' +
    '    var text=function(){return p.text.apply(p,arguments)};\n' +
    '    var textSize=function(){return p.textSize.apply(p,arguments)};\n' +
    '    var textAlign=function(){return p.textAlign.apply(p,arguments)};\n' +
    '    var textFont=function(){return p.textFont.apply(p,arguments)};\n' +
    '    var textStyle=function(){return p.textStyle.apply(p,arguments)};\n' +
    '    var textWidth=function(){return p.textWidth.apply(p,arguments)};\n' +
    '    var color=function(){return p.color.apply(p,arguments)};\n' +
    '    var lerpColor=function(){return p.lerpColor.apply(p,arguments)};\n' +
    '    var red=function(){return p.red.apply(p,arguments)};\n' +
    '    var green=function(){return p.green.apply(p,arguments)};\n' +
    '    var blue=function(){return p.blue.apply(p,arguments)};\n' +
    '    var alpha=function(){return p.alpha.apply(p,arguments)};\n' +
    '    var translate=function(){return p.translate.apply(p,arguments)};\n' +
    '    var rotate=function(){return p.rotate.apply(p,arguments)};\n' +
    '    var scale=function(){return p.scale.apply(p,arguments)};\n' +
    '    var map=function(){return p.map.apply(p,arguments)};\n' +
    '    var constrain=function(){return p.constrain.apply(p,arguments)};\n' +
    '    var lerp=function(){return p.lerp.apply(p,arguments)};\n' +
    '    var dist=function(){return p.dist.apply(p,arguments)};\n' +
    '    var noise=function(){return p.noise.apply(p,arguments)};\n' +
    '    var random=function(){return p.random.apply(p,arguments)};\n' +
    '    var frameCount=0;\n' +
    '    var mouseX=0,mouseY=0;\n' +
    '    var width=W,height=H;\n' +
    '    var PI=Math.PI,TWO_PI=Math.PI*2,HALF_PI=Math.PI/2,QUARTER_PI=Math.PI/4;\n' +
    '    var CENTER=p.CENTER,LEFT=p.LEFT,RIGHT=p.RIGHT,TOP=p.TOP,BOTTOM=p.BOTTOM,BASELINE=p.BASELINE;\n' +
    '    var BOLD=p.BOLD,NORMAL=p.NORMAL,ITALIC=p.ITALIC;\n' +
    '    var CLOSE=p.CLOSE;\n';

  return '\n' + p5Bindings +
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
    '    // p.background is NOT overridden — sanitizeCode rewrites all\n' +
    '    // p.background(...) to p.background(6,14,17) matching board bg.\n' +
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
    // Resize p5 after CSS transition completes (not a hardcoded timeout)
    var inst = animBox._p5Instance;
    if (inst && typeof inst.resizeCanvas === 'function') {
      figure.addEventListener('transitionend', function onEnd() {
        figure.removeEventListener('transitionend', onEnd);
        var r = animBox.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) {
          try { inst.resizeCanvas(Math.round(r.width), Math.round(r.height)); } catch(e) {}
        }
      });
      // Fallback if transition doesn't fire (e.g., no transition property)
      setTimeout(function() {
        var r = animBox.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) {
          try { inst.resizeCanvas(Math.round(r.width), Math.round(r.height)); } catch(e) {}
        }
      }, 400);
    }
    // Escape key closes fullscreen
    figure._escHandler = function(e) {
      if (e.key === 'Escape') { toggleAnimFullscreen(figure, animBox); }
    };
    document.addEventListener('keydown', figure._escHandler);
  }
}

async function createAnimation(cmd) {
  if (!cmd.code) return;

  // Auto-detect 3D: if code uses THREE.* APIs, route to Three.js renderer.
  var is3D = /\bTHREE\b|\.Scene\(\)|\.PerspectiveCamera|\.WebGLRenderer|\.Mesh\(|\.BoxGeometry|\.SphereGeometry|\.BufferGeometry|\.InstancedMesh|\.Points\(/.test(cmd.code);
  if (is3D) {
    return renderScene3D(cmd);
  }

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
  canvasWrap.style.cssText = 'width:100%;height:100%;overflow:hidden;';
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

  // Clear global skeleton — per-animation loader is about to appear
  if (typeof _clearHeavyDrawPending === 'function') _clearHeavyDrawPending();

  // Wait for the container to have a stable non-zero layout.
  // ResizeObserver fires when the element actually has dimensions,
  // which is more reliable than RAF-based guessing.
  var elRect;
  if (typeof ResizeObserver !== 'undefined') {
    elRect = await new Promise(function(resolve) {
      var settled = false;
      var ro = new ResizeObserver(function(entries) {
        var cr = entries[0].contentRect;
        if (cr.width > 0 && cr.height > 0 && !settled) {
          settled = true;
          ro.disconnect();
          resolve({ width: cr.width, height: cr.height });
        }
      });
      ro.observe(el);
      // Timeout fallback — don't hang if container is hidden
      setTimeout(function() {
        if (!settled) {
          settled = true;
          ro.disconnect();
          var r = el.getBoundingClientRect();
          resolve({ width: r.width, height: r.height });
        }
      }, 1000);
    });
  } else {
    // Fallback for browsers without ResizeObserver
    await new Promise(function(r) { requestAnimationFrame(function() { requestAnimationFrame(r); }); });
    elRect = el.getBoundingClientRect();
  }
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

  // Setup completion contract: the Promise resolves only after p5's
  // setup() has ACTUALLY executed (not just queued). This guarantees
  // AnimHelper exists before we register the animation entry, so figure
  // auto-sync can find it immediately when narration beats arrive.
  var inst;
  var setupComplete = new Promise(function(resolveSetup, rejectSetup) {
    try {
      inst = new p5(function(p) {
        try { sketchFn(p, pw, ph); } catch (err) {
          console.warn('[Animation] Sketch runtime error:', err.message);
          canvasWrap.innerHTML = '<div style="padding:12px;color:rgba(248,113,113,0.4);font-size:12px;font-family:monospace">Animation error: ' + escapeHtml(err.message) + '</div>';
          rejectSetup(err);
          return;
        }

        // Wrap draw() with board-bg fill + error boundary
        var userDraw = p.draw;
        if (userDraw) {
          var errors = 0;
          p.draw = function () {
            try { p.background(6, 14, 17); } catch (e) {}
            try { userDraw.call(p); } catch (err) {
              if (++errors === 1) console.warn('[Animation] draw() error:', err.message);
              if (errors >= 30) p.noLoop();
            }
          };
        }

        // Wrap setup() — runs AFTER user's createCanvas, so p.width/p.height
        // are correct. AnimHelper injection uses live dimensions.
        var userSetup = p.setup;
        p.setup = function () {
          // ALWAYS create canvas at container size FIRST. If the LLM's
          // code skipped setup entirely (goes straight to p.draw without
          // createCanvas), p5 defaults to 100x100 — way too small.
          // p5 handles double createCanvas gracefully (replaces canvas).
          try { p.createCanvas(pw, ph); } catch (e) {}
          if (userSetup) userSetup.call(p);
          try { if (!p._renderer.isP3D) p.textFont('sans-serif'); } catch (e) {}
          // Auto-inject AnimHelper AFTER createCanvas (p.width/height valid)
          if (!p._animHelper && typeof AnimHelper !== 'undefined' && !(p._renderer && p._renderer.isP3D)) {
            try {
              p._animHelper = new AnimHelper(p, p.width, p.height);
            } catch (e) { console.warn('[Animation] AnimHelper auto-inject failed:', e); }
          }
          p._setupComplete = true;
          resolveSetup();
        };
      }, canvasWrap);
    } catch (e) {
      console.warn('[Animation] Init error:', e.message);
      canvasWrap.innerHTML = '<div style="padding:12px;color:rgba(248,113,113,0.4);font-size:12px;font-family:monospace">Animation init error</div>';
      rejectSetup(e);
    }
  });

  // Wait for setup() to actually execute before registering the entry.
  // This is a CONTRACT — not a timing hack. The Promise resolves inside
  // p5's setup(), guaranteeing AnimHelper and canvas dimensions are ready.
  try {
    await Promise.race([setupComplete, new Promise(function(_, rej) { setTimeout(function() { rej(new Error('setup timeout')); }, 5000); })]);
  } catch (e) {
    console.warn('[Animation] Setup did not complete:', e.message);
    // Still register entry so cleanup works, but mark as incomplete
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
          try { p.createCanvas(Math.round(rect.width) || 300, Math.round(rect.height) || 200); } catch (e) {}
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
// FIGURE — animation on the left + narration column on the right.
// Each subsequent cmd:"narrate" with target=<figure id> appends one
// line into the narration column, animated char-by-char.
// ═══════════════════════════════════════════════════════════════

async function renderFigure(cmd) {
  if (!cmd.id) {
    console.warn('[Board] cmd:figure requires an id so cmd:narrate can target it');
    cmd.id = 'fig-' + Math.random().toString(36).slice(2, 8);
  }

  // Wrapper row holding [animation | narration]
  var wrapper = document.createElement('div');
  wrapper.className = 'bd-el bd-figure';
  wrapper.id = cmd.id;
  wrapper.dataset.cmd = 'figure';

  var hasAnimation = !!(cmd.code && cmd.code.trim());

  var animSlot = document.createElement('div');
  animSlot.className = 'bd-figure-anim';
  if (!hasAnimation) {
    // No animation code — hide the slot so narration gets full width
    animSlot.style.display = 'none';
  }
  wrapper.appendChild(animSlot);

  var narration = document.createElement('div');
  narration.className = 'bd-figure-narration';
  if (!hasAnimation) {
    // Full width narration when there's no animation
    narration.style.flex = '1 1 100%';
  }
  if (cmd.title) {
    var head = document.createElement('div');
    head.className = 'bd-figure-narration-title';
    head.textContent = cmd.title;
    narration.appendChild(head);
  }
  wrapper.appendChild(narration);

  // Place wrapper into the scene FIRST so child layout can measure
  placeElement(wrapper, cmd.placement || 'below', cmd);

  // Create animation inside the left slot (only if code was provided)
  if (hasAnimation) {
    var savedScene = board.liveScene;
    board.liveScene = animSlot;
    try {
      var animCmd = Object.assign({}, cmd, { id: cmd.id + '-anim', placement: 'below' });
      await createAnimation(animCmd);
    } finally {
      board.liveScene = savedScene;
    }
    // If animation creation failed (no canvas, no content), collapse the slot
    // so narration gets full width instead of showing a blank 65% area.
    if (!animSlot.querySelector('canvas') && !animSlot.querySelector('.bd-scene3d')) {
      animSlot.style.display = 'none';
      narration.style.flex = '1 1 100%';
    }
  }
}

// cmd:"narrate" is a thin convenience alias — equivalent to
// cmd:"text" placement:"figure:<target>". It exists so older prompts and
// the figure pattern doc still work. Internally it routes through
// renderText, which picks up the placement and lands the line inside the
// figure's narration column.
async function renderNarrate(cmd) {
  if (!cmd.target || !cmd.text) return;
  await renderText(Object.assign({}, cmd, {
    placement: 'figure:' + cmd.target,
    target: undefined,
  }));
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

  var contentCmds = ['text', 'latex', 'animation', 'figure', 'equation', 'step',
    'check', 'cross', 'callout', 'list', 'divider', 'mermaid', 'diagram',
    'split', 'flow', 'diff', 'question-block',
    'line', 'arrow', 'rect', 'fillrect', 'circle', 'arc', 'dot', 'dashed'];
  if (!cmd.placement && contentCmds.includes(cmd.cmd)) {
    cmd.placement = 'below';
  }

  switch (cmd.cmd) {
    case 'text':     await renderText(cmd); break;
    case 'h1':       await renderText(Object.assign({}, cmd, { size: 'h1' })); break;
    case 'h2':       await renderText(Object.assign({}, cmd, { size: 'h2' })); break;
    case 'h3':       await renderText(Object.assign({}, cmd, { size: 'h3' })); break;
    case 'gap':      renderGap(cmd); break;
    case 'note':     await renderText(Object.assign({}, cmd, { size: 'small', color: cmd.color || 'dim' })); break;
    case 'latex':    await renderEquation(cmd); break;
    case 'equation': await renderEquation(cmd); break;
    case 'step':     await renderStep(cmd); break;
    case 'check':    await renderCheckCross(cmd, true); break;
    case 'cross':    await renderCheckCross(cmd, false); break;
    case 'callout':  await renderCallout(cmd); break;
    case 'result':   await renderCallout(Object.assign({}, cmd, { text: (cmd.label ? cmd.label + ': ' : '') + (cmd.text || ''), color: cmd.color || 'gold' })); break;
    case 'connect':  renderConnect(cmd); break;
    case 'mermaid':  await renderMermaid(cmd); break;
    case 'list':     await renderList(cmd); break;
    case 'divider':  renderDivider(cmd); break;
    case 'animation': await createAnimation(cmd); break;
    case 'figure':   await renderFigure(cmd); break;
    case 'narrate':  await renderNarrate(cmd); break;
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
    case 'split':    await renderSplit(cmd); break;
    case 'flow':     renderFlow(cmd); break;
    case 'flow-add': renderFlowAdd(cmd); break;
    case 'diff':     await renderDiff(cmd); break;
    case 'diff-add': renderDiffAdd(cmd); break;
    case 'question-block': await renderQuestion(cmd); break;
    case 'code':     await renderCode(cmd); break;
    case 'code-highlight': _codeHighlightLines(cmd); break;
    case 'run':      _runStudentCode(cmd.target); break;
    case 'scene3d':  await renderScene3D(cmd); break;
    default:
      console.warn('[Board] Unknown command:', cmd.cmd);
  }

  autoScroll();
}

// ── Code block — read-only OR editable OR runnable+tests ───────────
//
// One command, three modes (chosen by flags):
//
//   {cmd:"code", lang:"python", text:"..."}                   → read-only
//   {cmd:"code", ..., editable:true}                          → worksheet (no run)
//   {cmd:"code", ..., editable:true, runnable:true,           → full runner
//                     tests:[{in,out},...]}
//
// State for editable/runnable variants lives in board.codeRunners[id]
// and gets shipped to the tutor via buildContext() on the next message.
async function renderCode(cmd) {
  // Auto-generate an id if the model forgot — editable/runnable runners
  // MUST have an id so the registry can track them and buildContext()
  // can ship the state to the tutor. Without an id the runner is invisible.
  if ((cmd.editable || cmd.runnable) && !cmd.id) {
    cmd.id = 'code-' + Math.random().toString(36).slice(2, 8);
    console.warn('[CodeRunner] Auto-generated id:', cmd.id, '— model should set id explicitly for editable/runnable code blocks.');
  }

  var el = createElement('div', cmd, 'bd-code-block');
  var isEditable = !!cmd.editable;
  var isRunnable = !!cmd.runnable;
  var hasTests = Array.isArray(cmd.tests) && cmd.tests.length > 0;
  if (isEditable || isRunnable || hasTests) el.classList.add('bd-code-runner');

  // Header — language pill, optional filename, action buttons
  var header = document.createElement('div');
  header.className = 'bd-code-header';
  var langText = (cmd.lang || 'text').toUpperCase();
  var headerInner = '<span class="bd-code-lang">' + escapeHtml(langText) + '</span>';
  if (cmd.filename) headerInner += '<span class="bd-code-file">' + escapeHtml(cmd.filename) + '</span>';
  if (isEditable && !isRunnable) headerInner += '<span class="bd-code-prompt">edit me</span>';
  if (isRunnable) headerInner += '<span class="bd-code-prompt">edit and run</span>';
  header.innerHTML = headerInner;

  // Action buttons (Reset, Run) for interactive variants. The actual
  // wiring happens after el is fully built so the buttons can find the
  // body element via querySelector.
  var resetBtn = null, runBtn = null;
  if (isEditable || isRunnable) {
    var actions = document.createElement('div');
    actions.className = 'bd-code-actions';
    resetBtn = document.createElement('button');
    resetBtn.className = 'bd-code-btn bd-code-btn-reset';
    resetBtn.textContent = '↺ Reset';
    actions.appendChild(resetBtn);
    if (isRunnable) {
      runBtn = document.createElement('button');
      runBtn.className = 'bd-code-btn bd-code-btn-run';
      runBtn.textContent = '▶ Run';
      actions.appendChild(runBtn);
    }
    header.appendChild(actions);
  }
  el.appendChild(header);

  // Normalize literal escape sequences. The model often double-escapes
  // newlines inside the JSON `text` field — JSON.parse hands us the
  // 2-char string \n (backslash + n) instead of a real newline. Convert
  // them all so split('\n') works no matter how the model escaped them.
  var text = cmd.text || '';
  if (typeof text === 'string' && text.indexOf('\\') !== -1) {
    text = text
      .replace(/\\n/g, '\n')
      .replace(/\\r/g, '\r')
      .replace(/\\t/g, '\t');
  }

  // Body — always a <pre>, even for editable variants. Using <div> causes
  // newlines to collapse when highlight.js sets innerHTML with span markup
  // (the HTML parser treats \n as inter-element whitespace in a div, but
  // preserves it in a pre). <pre contenteditable="true"> works in all
  // browsers and preserves whitespace correctly.
  var body = document.createElement('pre');
  body.className = 'bd-code-body';
  el.appendChild(body);
  if (isEditable) {
    body.setAttribute('contenteditable', 'true');
    body.setAttribute('spellcheck', 'false');
    body.dataset.codeId = cmd.id || '';
  }

  // Tests panel — placeholder rows; status fills in after Run
  if (hasTests) {
    var testsBlock = document.createElement('div');
    testsBlock.className = 'bd-code-tests';
    var testsHeader = document.createElement('div');
    testsHeader.className = 'bd-code-tests-header';
    testsHeader.innerHTML = 'Test cases <span class="bd-code-tests-summary idle" data-tests-summary>not run yet</span>';
    testsBlock.appendChild(testsHeader);
    var table = document.createElement('table');
    table.className = 'bd-code-tests-table';
    table.innerHTML = '<thead><tr><th></th><th>Input</th><th>Expected</th><th>Got</th></tr></thead>';
    var tbody = document.createElement('tbody');
    cmd.tests.forEach(function(t, i) {
      var row = document.createElement('tr');
      row.dataset.testIdx = String(i);
      row.innerHTML = '<td class="bd-code-tests-status">·</td>' +
                      '<td>' + escapeHtml(String(t.in || '')) + '</td>' +
                      '<td>' + escapeHtml(String(t.out || '')) + '</td>' +
                      '<td class="bd-code-tests-actual">—</td>';
      tbody.appendChild(row);
    });
    table.appendChild(tbody);
    testsBlock.appendChild(table);
    el.appendChild(testsBlock);
  }

  // Output panel — empty by default for runnable, populated on Run
  if (isRunnable) {
    var output = document.createElement('div');
    output.className = 'bd-code-output bd-code-output-empty';
    output.innerHTML = '<span class="bd-code-output-empty-text">Click <strong>Run</strong> to execute · last result: never</span>';
    el.appendChild(output);
  }

  placeElement(el, cmd.placement, cmd);

  // Animate the body content char-by-char like the rest of the board.
  // Default is 20ms/char (~50 chars/sec): a 40-char line types in ~0.8s.
  // For editable runners, suppress the input listener while typing so
  // the listener doesn't fire 200 times during the animation.
  var typingDelay = cmd.charDelay !== undefined ? cmd.charDelay : 20;
  body._suppressInput = true;
  await animateText(body, text, { charDelay: typingDelay });
  body._suppressInput = false;

  // Store the raw text with proper newlines so _highlightCodeBody can
  // read it instead of body.textContent (which loses \n after animateText
  // converts them to <br> tags).
  body.dataset.rawText = text;

  // Syntax highlight after the typing animation completes.
  _highlightCodeBody(body, cmd.lang);

  // Wrap lines with line numbers + optional highlight. This runs AFTER
  // highlight.js so the span markup gets wrapped inside line containers.
  _wrapCodeLines(body, cmd.highlight);

  // Wire the editable listeners AFTER the typing animation completes,
  // so the student can immediately start editing without the listener
  // having fired hundreds of times during the type-on.
  if (isEditable) {
    body.addEventListener('input', function() {
      if (body._suppressInput) return;
      var id = body.dataset.codeId;
      if (!id || !board.codeRunners[id]) return;
      board.codeRunners[id].currentCode = body.innerText.replace(/\u00a0/g, ' ');
      board.codeRunners[id].lastInteractedAt = Date.now();
    });
    // Tab key inserts 4 spaces instead of jumping focus
    body.addEventListener('keydown', function(e) {
      if (e.key === 'Tab') {
        e.preventDefault();
        document.execCommand('insertText', false, '    ');
      }
    });
    // Re-highlight when the student clicks away. While typing, the
    // highlight spans get stale (cursor would jump if we re-tokenized
    // mid-edit), but on blur it's safe to refresh the colors.
    body.addEventListener('blur', function() {
      var id = body.dataset.codeId;
      var entry = id && board.codeRunners[id];
      if (!entry) return;
      // Snapshot text first — innerText translates <br> back to \n
      var currentText = body.innerText.replace(/\u00a0/g, ' ');
      entry.currentCode = currentText;
      body.dataset.rawText = currentText;
      body.classList.remove('hljs');
      _highlightCodeBody(body, entry.lang);
      _wrapCodeLines(body, null);
    });
  }

  // Register the runner in board.codeRunners. buildContext() reads from
  // here on every student MESSAGE event and ships the snapshot to the
  // tutor — no separate WS event, no tool call.
  if ((isEditable || isRunnable) && cmd.id) {
    board.codeRunners = board.codeRunners || {};
    board.codeRunners[cmd.id] = {
      id: cmd.id,
      lang: cmd.lang || 'text',
      editable: isEditable,
      runnable: isRunnable,
      originalCode: text,
      currentCode: text,
      tests: cmd.tests ? { spec: cmd.tests, results: null } : null,
      lastRun: null,
      lastInteractedAt: Date.now(),
      element: el,
    };
  }

  // Wire the Reset button — restore the original tutor-provided code.
  if (resetBtn) {
    resetBtn.addEventListener('click', function() {
      var entry = board.codeRunners && board.codeRunners[cmd.id];
      if (!entry) return;
      body.textContent = entry.originalCode;
      body.dataset.rawText = entry.originalCode;
      body.classList.remove('hljs');
      _highlightCodeBody(body, entry.lang);
      _wrapCodeLines(body, null);
      entry.currentCode = entry.originalCode;
      entry.lastRun = null;
      if (entry.tests) entry.tests.results = null;
      entry.lastInteractedAt = Date.now();
      // Reset visible test/output panels too
      _resetCodeRunnerPanels(el);
    });
  }

  // Wire the Run button — Step 3 plugs in actual execution. For now,
  // just flash a "running…" state and leave the panels reset.
  if (runBtn) {
    runBtn.addEventListener('click', function() {
      _runStudentCode(cmd.id);
    });
  }
}

// Reset the visible tests/output panels of a runner element to their
// "no run yet" state. Used by Reset button and at the start of each Run.
function _resetCodeRunnerPanels(el) {
  var output = el.querySelector('.bd-code-output');
  if (output) {
    output.className = 'bd-code-output bd-code-output-empty';
    output.innerHTML = '<span class="bd-code-output-empty-text">Click <strong>Run</strong> to execute · last result: never</span>';
  }
  var summary = el.querySelector('[data-tests-summary]');
  if (summary) {
    summary.className = 'bd-code-tests-summary idle';
    summary.textContent = 'not run yet';
  }
  var rows = el.querySelectorAll('.bd-code-tests-table tbody tr');
  rows.forEach(function(row) {
    row.classList.remove('pass-row', 'fail-row');
    var status = row.querySelector('.bd-code-tests-status');
    if (status) status.textContent = '·';
    var actual = row.querySelector('.bd-code-tests-actual');
    if (actual) actual.textContent = '—';
  });
}

// Append-only char-by-char animator for code-block growth.
// Unlike animateText (which clobbers parentEl at the end), this APPENDS
// new characters into the parent without touching existing content. Used
// when cmd:"update" extends code line by line — the previously-typed
// lines must stay put while the new suffix types in below them.
async function _animateAppend(parentEl, text, opts) {
  if (!text) return;
  var delay = (opts && opts.charDelay !== undefined) ? opts.charDelay : 8;
  // Strip any highlight markup off the existing content first, so the
  // new chars land as plain text alongside plain text. We re-highlight
  // the whole body once the append is done.
  if (parentEl.classList.contains('hljs')) {
    parentEl.textContent = parentEl.textContent;
    parentEl.classList.remove('hljs');
  }
  // Append a text node, then mutate it char-by-char. Faster than
  // creating a new node per character and produces the same visual.
  var node = document.createTextNode('');
  parentEl.appendChild(node);
  for (var i = 0; i < text.length; i++) {
    if (board.cancelFlag) break;
    node.appendData(text[i]);
    // Auto-scroll the code body so new lines stay visible as they type
    if (text[i] === '\n') {
      parentEl.scrollTop = parentEl.scrollHeight;
    }
    if (delay > 0) {
      await new Promise(function(r) { setTimeout(r, delay); });
    }
  }
  // Final scroll to bottom after the last char
  parentEl.scrollTop = parentEl.scrollHeight;
}

// ═══════════════════════════════════════════════════════════════
// SYNTAX HIGHLIGHTING via highlight.js (lazy-loaded on first code).
// ~30 KB core from CDN, language definitions are bundled with the
// "common" build so we get Python, JS, Java, C++, SQL, Go, Rust,
// TypeScript, etc. out of the box. Theme is injected inline below
// so it matches the chalkboard palette without a second CDN load.
// ═══════════════════════════════════════════════════════════════

var _hljsLoading = null;
function _loadHighlightJs() {
  if (typeof hljs !== 'undefined') return Promise.resolve(hljs);
  if (_hljsLoading) return _hljsLoading;
  _hljsLoading = new Promise(function(resolve, reject) {
    var s = document.createElement('script');
    s.src = 'https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.10.0/build/highlight.min.js';
    s.onload = function() {
      _injectHighlightTheme();
      // eslint-disable-next-line no-undef
      resolve(typeof hljs !== 'undefined' ? hljs : null);
    };
    s.onerror = function() { reject(new Error('Failed to load highlight.js')); };
    document.head.appendChild(s);
  });
  return _hljsLoading;
}

// Custom theme — matches the chalkboard palette (mint/gold/cyan/red on
// dark grey). Injected once after highlight.js loads. Avoids a second
// CDN round-trip for a stylesheet.
function _injectHighlightTheme() {
  if (document.getElementById('bd-hljs-theme')) return;
  var style = document.createElement('style');
  style.id = 'bd-hljs-theme';
  style.textContent = [
    '.bd-code-body .hljs { color: #e6edf3; background: transparent; padding: 0; }',
    '.bd-code-body .hljs-comment, .bd-code-body .hljs-quote { color: #6272a4; font-style: italic; }',
    '.bd-code-body .hljs-keyword, .bd-code-body .hljs-selector-tag, .bd-code-body .hljs-built_in,',
    '.bd-code-body .hljs-name, .bd-code-body .hljs-tag, .bd-code-body .hljs-meta { color: #ff79c6; }',
    '.bd-code-body .hljs-string, .bd-code-body .hljs-title.class_, .bd-code-body .hljs-attr,',
    '.bd-code-body .hljs-symbol, .bd-code-body .hljs-bullet, .bd-code-body .hljs-addition { color: #f1fa8c; }',
    '.bd-code-body .hljs-number, .bd-code-body .hljs-literal { color: #bd93f9; }',
    '.bd-code-body .hljs-title, .bd-code-body .hljs-section, .bd-code-body .hljs-title.function_ { color: #50fa7b; }',
    '.bd-code-body .hljs-variable, .bd-code-body .hljs-template-variable, .bd-code-body .hljs-attribute { color: #f8f8f2; }',
    '.bd-code-body .hljs-type, .bd-code-body .hljs-class .hljs-title { color: #8be9fd; }',
    '.bd-code-body .hljs-deletion, .bd-code-body .hljs-formula { color: #ff5555; }',
    '.bd-code-body .hljs-operator, .bd-code-body .hljs-punctuation { color: #ff79c6; }',
    '.bd-code-body .hljs-params { color: #ffb86c; font-style: italic; }',
    '.bd-code-body .hljs-property { color: #A8E6CF; }',
  ].join('\n');
  document.head.appendChild(style);
}

// Highlight a code body in place. Safe to call multiple times — the
// last call wins. Strips any existing markup and re-tokenizes from the
// current text content (so it works for both initial render and after
// an animated update).
function _highlightCodeBody(body, lang) {
  if (!body) return;
  if (typeof hljs === 'undefined') {
    _loadHighlightJs().then(function() { _highlightCodeBody(body, lang); }).catch(function(e) {
      console.warn('[CodeRunner] highlight.js load failed:', e.message);
    });
    return;
  }
  try {
    // Read from dataset.rawText (authoritative source with proper \n),
    // NOT from body.textContent — because animateText converts \n to <br>
    // in its final innerHTML assignment, and textContent doesn't translate
    // <br> back to \n. Without this, highlighting gets a flat one-liner.
    var text = body.dataset.rawText || body.textContent || '';
    if (!text.trim()) return;
    var langKey = (lang || '').toLowerCase();
    var result;
    if (langKey && hljs.getLanguage(langKey)) {
      result = hljs.highlight(text, { language: langKey, ignoreIllegals: true });
    } else {
      result = hljs.highlightAuto(text);
    }
    body.innerHTML = result.value;
    body.classList.add('hljs');
  } catch (e) {
    console.warn('[CodeRunner] highlight failed:', e && e.message);
  }
}

// Wrap each line of the code body's innerHTML in a <span class="bd-code-line">
// element. Each line gets a data-ln attribute for the line number (shown
// via CSS ::before) and optionally a highlight class (transparent mint
// background) if the line number is in the highlightLines array.
//
// MUST run AFTER _highlightCodeBody so the highlighted HTML (span tokens)
// gets wrapped inside line containers, not the other way around.
function _wrapCodeLines(body, highlightLines) {
  if (!body) return;
  var html = body.innerHTML;
  if (!html || !html.trim()) return;
  // Split on actual newlines in the HTML source. hljs preserves \n
  // between span tokens, and <pre> preserves them in innerHTML.
  var lines = html.split('\n');
  // Don't wrap if there's only a trailing empty line (common)
  if (lines.length > 1 && lines[lines.length - 1].trim() === '') {
    lines.pop();
  }
  var hiSet = {};
  if (highlightLines && Array.isArray(highlightLines)) {
    for (var h = 0; h < highlightLines.length; h++) hiSet[highlightLines[h]] = true;
  }
  body.innerHTML = lines.map(function(lineHtml, i) {
    var lineNum = i + 1;
    var hiClass = hiSet[lineNum] ? ' bd-code-line-hi' : '';
    return '<span class="bd-code-line' + hiClass + '" data-ln="' + lineNum + '">' + (lineHtml || ' ') + '</span>';
  }).join('\n');
}

// cmd:"code-highlight" — update which lines are highlighted on an
// existing code block. Tutor uses this to draw attention to specific
// lines while speaking: {"cmd":"code-highlight","target":"bs","lines":[3,7]}
function _codeHighlightLines(cmd) {
  if (!cmd.target) return;
  var el = document.getElementById(cmd.target);
  if (!el || !el.classList.contains('bd-code-block')) return;
  var body = el.querySelector('.bd-code-body');
  if (!body) return;
  // Re-wrap with the new highlight set. Need to unwrap first if already
  // wrapped — easiest to re-highlight + re-wrap from rawText.
  var entry = board.codeRunners && board.codeRunners[cmd.target];
  var lang = entry ? entry.lang : null;
  var rawText = body.dataset.rawText || body.textContent || '';
  body.textContent = rawText;
  body.classList.remove('hljs');
  body.dataset.rawText = rawText;
  _highlightCodeBody(body, lang);
  _wrapCodeLines(body, cmd.lines || []);
}

// ═══════════════════════════════════════════════════════════════
// PYTHON EXECUTION via Pyodide (lazy-loaded on first run).
// Pyodide is a 6 MB CDN bundle — only loaded when the student
// actually clicks Run on a Python runner. Cached for the rest of
// the session. Future phases can add JS / SQL runtimes here.
// ═══════════════════════════════════════════════════════════════

var _pyodideInstance = null;
var _pyodideLoading = null;

function _loadPyodide() {
  if (_pyodideInstance) return Promise.resolve(_pyodideInstance);
  if (_pyodideLoading) return _pyodideLoading;

  _pyodideLoading = new Promise(function(resolve, reject) {
    if (typeof loadPyodide !== 'undefined') {
      // Pyodide already loaded
      loadPyodide({ indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.26.4/full/' })
        .then(function(py) { _pyodideInstance = py; resolve(py); })
        .catch(reject);
      return;
    }
    // Inject the CDN script
    var script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js';
    script.onload = function() {
      // eslint-disable-next-line no-undef
      loadPyodide({ indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.26.4/full/' })
        .then(function(py) { _pyodideInstance = py; resolve(py); })
        .catch(reject);
    };
    script.onerror = function() { reject(new Error('Failed to load Pyodide CDN')); };
    document.head.appendChild(script);
  });
  return _pyodideLoading;
}

// Render the "running" placeholder in the output panel.
function _showRunnerLoading(el, msg) {
  var output = el.querySelector('.bd-code-output');
  if (!output) return;
  output.className = 'bd-code-output bd-code-output-empty';
  output.innerHTML = '<div class="bd-code-output-header"><span class="bd-code-output-status-dot running"></span>' + escapeHtml(msg || 'Running…') + '</div>';
}

// Update the visible test rows + summary after a run completes.
function _updateTestRows(el, results) {
  if (!results) return;
  var rows = el.querySelectorAll('.bd-code-tests-table tbody tr');
  results.forEach(function(r, i) {
    var row = rows[i];
    if (!row) return;
    row.classList.remove('pass-row', 'fail-row');
    row.classList.add(r.pass ? 'pass-row' : 'fail-row');
    var status = row.querySelector('.bd-code-tests-status');
    if (status) status.textContent = r.pass ? '✓' : '✗';
    var actual = row.querySelector('.bd-code-tests-actual');
    if (actual) actual.textContent = r.actual === undefined || r.actual === null ? '—' : String(r.actual);
  });
  var summary = el.querySelector('[data-tests-summary]');
  if (summary) {
    var passed = results.filter(function(r) { return r.pass; }).length;
    var total = results.length;
    summary.className = 'bd-code-tests-summary ' + (passed === total ? 'ok' : 'err');
    summary.textContent = passed + ' / ' + total + ' passed';
  }
}

// Render the run output (stdout + status header) into the output panel.
function _showRunResult(el, result) {
  var output = el.querySelector('.bd-code-output');
  if (!output) return;
  if (result.status === 'success') {
    output.className = 'bd-code-output bd-code-output-ok';
    var header = '<div class="bd-code-output-header"><span class="bd-code-output-status-dot ok"></span>Run succeeded · ' + (result.elapsedMs || 0) + 'ms</div>';
    output.innerHTML = header + escapeHtml(result.stdout || '(no output)');
  } else {
    output.className = 'bd-code-output bd-code-output-err';
    var hdr = '<div class="bd-code-output-header"><span class="bd-code-output-status-dot err"></span>Run failed · ' + (result.elapsedMs || 0) + 'ms</div>';
    var body = (result.stderr || result.error || 'Unknown error');
    if (result.stdout) body = escapeHtml(result.stdout) + '\n\n' + escapeHtml(body);
    else body = escapeHtml(body);
    output.innerHTML = hdr + body;
  }
}

// Top-level entry point — wired to the Run button AND the model's
// cmd:"run" beat command. Loads Pyodide if needed, executes the code,
// runs the tests, updates UI + state.codeRunners[id].lastRun.
async function _runStudentCode(id) {
  if (!id) { console.warn('[CodeRunner] _runStudentCode called with no id'); return; }
  var entry = board.codeRunners && board.codeRunners[id];
  if (!entry) { console.warn('[CodeRunner] No runner registered for id:', id); return; }
  if (!entry.runnable) {
    console.warn('[CodeRunner] Runner', id, 'is not runnable (no Run button)');
    return;
  }
  var el = entry.element;
  if (!el) return;

  // Disable the Run button while executing
  var runBtn = el.querySelector('.bd-code-btn-run');
  if (runBtn) { runBtn.disabled = true; runBtn.textContent = 'running…'; }
  _showRunnerLoading(el, _pyodideInstance ? 'Running Python…' : 'Loading Pyodide (first run, ~3-5s)…');

  var startTime = Date.now();
  try {
    var py = await _loadPyodide();
    if (entry.lang !== 'python') {
      throw new Error('Only Python is supported in Phase 1. Got: ' + entry.lang);
    }

    var code = entry.currentCode;
    var testSpec = entry.tests && entry.tests.spec;

    // Capture stdout/stderr by redirecting sys.stdout/stderr to StringIO,
    // then run the user code. If tests are provided, run each test
    // independently and capture the result of evaluating the test input
    // as a function call. Tests format: {in: "func(args)", out: "expected"}.
    var pyResult;
    if (testSpec && testSpec.length > 0) {
      pyResult = await _runWithTests(py, code, testSpec);
    } else {
      pyResult = await _runOnce(py, code);
    }

    var elapsed = Date.now() - startTime;
    pyResult.elapsedMs = elapsed;
    pyResult.ranAt = new Date().toISOString();

    // Update entry state
    entry.lastRun = {
      status: pyResult.status,
      stdout: pyResult.stdout || '',
      stderr: pyResult.stderr || '',
      errorLine: pyResult.errorLine || null,
      elapsedMs: elapsed,
      ranAt: pyResult.ranAt,
    };
    if (pyResult.testResults) {
      entry.tests.results = pyResult.testResults;
    }
    entry.lastInteractedAt = Date.now();

    // Update UI
    if (pyResult.testResults) _updateTestRows(el, pyResult.testResults);
    _showRunResult(el, pyResult);
  } catch (err) {
    console.error('[CodeRunner] Run failed:', err);
    var elapsed = Date.now() - startTime;
    entry.lastRun = {
      status: 'error',
      stdout: '',
      stderr: err && err.message ? err.message : String(err),
      elapsedMs: elapsed,
      ranAt: new Date().toISOString(),
    };
    _showRunResult(el, {
      status: 'error',
      error: 'Failed to start: ' + (err && err.message ? err.message : String(err)),
      elapsedMs: elapsed,
    });
  } finally {
    if (runBtn) { runBtn.disabled = false; runBtn.textContent = '▶ Run'; }
  }
}

// Run the code once, capture stdout/stderr, return {status, stdout, stderr}.
async function _runOnce(py, code) {
  py.runPython([
    'import sys, io, traceback',
    '_capture_stdout = io.StringIO()',
    '_capture_stderr = io.StringIO()',
    'sys.stdout = _capture_stdout',
    'sys.stderr = _capture_stderr',
  ].join('\n'));
  try {
    await py.runPythonAsync(code);
    var stdout = py.runPython('_capture_stdout.getvalue()');
    var stderr = py.runPython('_capture_stderr.getvalue()');
    return { status: 'success', stdout: stdout, stderr: stderr };
  } catch (err) {
    // Capture any stdout/stderr written BEFORE the crash — the student
    // might have print() calls that ran before the error line.
    var capturedStdout = '', capturedStderr = '';
    try {
      capturedStdout = py.runPython('_capture_stdout.getvalue()');
      capturedStderr = py.runPython('_capture_stderr.getvalue()');
    } catch (e) { /* ignore — capture buffers may be unavailable */ }

    // Extract the FULL traceback from the Pyodide PythonError.
    // err.message may be just "PythonError" (the JS wrapper type).
    // The actual Python traceback is usually in the longer of
    // err.message vs String(err). Some Pyodide versions also expose
    // err.type (the Python exception class name).
    var errMsg = String(err);
    if (err && err.message && err.message.length > errMsg.length) {
      errMsg = err.message;
    }
    // Strip the "PythonError: " prefix if present — the traceback
    // itself is more useful than the JS wrapper class name.
    errMsg = errMsg.replace(/^PythonError:\s*/i, '');

    // Combine captured stderr (from explicit stderr writes) with the
    // traceback from the exception.
    var fullStderr = capturedStderr
      ? capturedStderr.trim() + '\n\n' + errMsg
      : errMsg;

    var lineMatch = fullStderr.match(/line (\d+)/);
    return {
      status: 'error',
      stdout: capturedStdout,
      stderr: fullStderr,
      errorLine: lineMatch ? parseInt(lineMatch[1], 10) : null,
    };
  } finally {
    try { py.runPython('sys.stdout = sys.__stdout__\nsys.stderr = sys.__stderr__'); } catch (e) {}
  }
}

// Run the code, then evaluate each test case as a Python expression and
// compare against the expected string. Returns {status, stdout, testResults}.
async function _runWithTests(py, code, testSpec) {
  // First, define the user's code in the Python namespace
  py.runPython([
    'import sys, io',
    '_capture_stdout = io.StringIO()',
    '_capture_stderr = io.StringIO()',
    'sys.stdout = _capture_stdout',
    'sys.stderr = _capture_stderr',
  ].join('\n'));

  var defineErr = null;
  try {
    await py.runPythonAsync(code);
  } catch (err) {
    var errStr = String(err);
    if (err && err.message && err.message.length > errStr.length) errStr = err.message;
    defineErr = errStr.replace(/^PythonError:\s*/i, '');
  }

  var stdoutAfterDefine = '';
  try { stdoutAfterDefine = py.runPython('_capture_stdout.getvalue()'); } catch (e) {}
  try { py.runPython('sys.stdout = sys.__stdout__\nsys.stderr = sys.__stderr__'); } catch (e) {}

  if (defineErr) {
    return { status: 'error', stdout: stdoutAfterDefine, stderr: defineErr, testResults: null };
  }

  // Now run each test as: repr(eval(test.in)) == test.out (string match)
  var testResults = [];
  var anyFailed = false;
  for (var i = 0; i < testSpec.length; i++) {
    var t = testSpec[i];
    var input = t.in || '';
    var expected = String(t.out !== undefined ? t.out : '');
    var actual = '';
    var pass = false;
    try {
      // Eval the input expression — e.g. "binary_search([1,3,5], 5)"
      var raw = py.runPython('repr(' + input + ')');
      // Strip quotes if it's a string repr ('5' → 5) so simple int matches work
      if (raw.length >= 2 && raw[0] === "'" && raw[raw.length - 1] === "'") {
        actual = raw.slice(1, -1);
      } else {
        actual = raw;
      }
      pass = (actual === expected);
    } catch (err) {
      actual = 'Error: ' + (err && err.message ? err.message : String(err));
      pass = false;
    }
    if (!pass) anyFailed = true;
    testResults.push({ input: input, expected: expected, actual: actual, pass: pass });
  }

  return {
    status: anyFailed ? 'error' : 'success',
    stdout: stdoutAfterDefine,
    stderr: anyFailed ? (testResults.length - testResults.filter(function(r) { return r.pass; }).length) + ' of ' + testResults.length + ' tests failed' : '',
    testResults: testResults,
  };
}

function escapeHtml(t) {
  return String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── Three.js 3D scene — production quality rendering ────────────────
async function renderScene3D(cmd) {
  var container = createElement('div', cmd, 'bd-scene3d');
  container.style.width = '100%';
  container.style.maxWidth = (cmd.width || 700) + 'px';
  container.style.height = (cmd.height || 450) + 'px';
  container.style.borderRadius = '10px';
  container.style.overflow = 'visible';
  container.style.border = 'none';
  container.style.background = '#060e11';
  container.style.position = 'relative';
  container.style.touchAction = 'none';
  container.style.userSelect = 'none';
  placeElement(container, cmd.placement, cmd);

  // Loading indicator
  container.innerHTML = '<div class="bd-anim-loading"><div class="bd-anim-loading-bars"><div></div><div></div><div></div></div>' +
    '<div class="bd-anim-loading-text">Euler is drawing: ' + escapeHtml(cmd.title || '3D scene') + '</div></div>';

  // Clear global skeleton — per-animation loader is now visible
  if (typeof _clearHeavyDrawPending === 'function') _clearHeavyDrawPending();

  // YIELD — let the browser paint the loading indicator
  await new Promise(function(r) { requestAnimationFrame(function() { requestAnimationFrame(r); }); });

  if (typeof THREE === 'undefined') {
    container.innerHTML = '<div class="bd-3d-fallback"><div class="bd-3d-fallback-icon">&#9674;</div>' +
      '<span>3D: ' + escapeHtml(cmd.title || 'visualization') + '</span>' +
      '<span class="bd-3d-fallback-sub">Interactive 3D not available</span></div>';
    return;
  }

  // Clear loading, build canvas — no controls bar (was blocking drag)
  container.innerHTML = '';

  // Title + legend as a small translucent overlay on top of canvas
  if (cmd.title || (cmd.legend && cmd.legend.length)) {
    var overlay = document.createElement('div');
    overlay.style.cssText = 'position:absolute;top:8px;left:10px;z-index:2;pointer-events:none;font-family:var(--bd-font,sans-serif);';
    if (cmd.title) {
      overlay.innerHTML += '<div style="font-size:11px;color:rgba(255,255,255,0.4);margin-bottom:4px">' + escapeHtml(cmd.title) + '</div>';
    }
    if (cmd.legend && cmd.legend.length) {
      overlay.innerHTML += '<div style="display:flex;gap:10px;flex-wrap:wrap;font-size:10px;color:rgba(255,255,255,0.35)">' +
        cmd.legend.map(function(l) {
          return '<span style="display:flex;align-items:center;gap:4px"><span style="width:6px;height:6px;border-radius:50%;background:' + (l.color || '#fff') + '"></span>' + escapeHtml(l.text || l.label || '') + '</span>';
        }).join('') + '</div>';
    }
    container.appendChild(overlay);
  }

  var rect = container.getBoundingClientRect();
  var w = Math.round(rect.width) || cmd.width || 700;
  var h = Math.round(rect.height) || cmd.height || 450;
  var scene = new THREE.Scene();
  scene.background = new THREE.Color(0x060e11);
  var camera = new THREE.PerspectiveCamera(45, w / h, 0.01, 500);
  camera.position.set(cmd.cameraX || 0, cmd.cameraY || 2, cmd.cameraZ || 24);
  camera.lookAt(0, 0, 0);

  var threeRenderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  threeRenderer.setSize(w, h);
  threeRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  threeRenderer.setClearColor(0x060e11, 1);
  threeRenderer.domElement.style.pointerEvents = 'auto';
  threeRenderer.domElement.style.touchAction = 'none';
  threeRenderer.domElement.style.cursor = 'grab';
  threeRenderer.domElement.style.userSelect = 'none';
  // Stop mouse events from propagating to parent scrollable containers
  // (the board has overflow-y scroll which intercepts drag gestures)
  threeRenderer.domElement.addEventListener('mousedown', function(e) {
    e.stopPropagation();
    threeRenderer.domElement.style.cursor = 'grabbing';
  });
  threeRenderer.domElement.addEventListener('mouseup', function() {
    threeRenderer.domElement.style.cursor = 'grab';
  });
  threeRenderer.domElement.addEventListener('wheel', function(e) {
    e.stopPropagation(); // prevent board scroll on zoom
  }, { passive: false });
  container.appendChild(threeRenderer.domElement);

  // Orbit controls
  var controls = null;
  if (THREE.OrbitControls) {
    controls = new THREE.OrbitControls(camera, threeRenderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.autoRotate = cmd.autoRotate !== false;
    controls.autoRotateSpeed = cmd.rotateSpeed || 1;
    controls.enableZoom = true;
    controls.enablePan = true;
  }

  // High-quality lighting
  scene.add(new THREE.AmbientLight(0xffffff, 0.42));
  var dir1 = new THREE.DirectionalLight(0xffffff, 0.9);
  dir1.position.set(6, 12, 9);
  scene.add(dir1);
  var dir2 = new THREE.DirectionalLight(0x3355ff, 0.28);
  dir2.position.set(-6, -4, 5);
  scene.add(dir2);

  // Grid/axes only if explicitly requested
  if (cmd.grid === true) scene.add(new THREE.GridHelper(10, 10, 0x1a3a2a, 0x111413));
  if (cmd.axes === true) scene.add(new THREE.AxesHelper(2));

  // RAF interception for LLM animation loops
  var pendingRAFs = [], rafIdCounter = 1, rafIdMap = {};
  function interceptedRAF(cb) { var id = rafIdCounter++; rafIdMap[id] = cb; pendingRAFs.push(id); return id; }
  function interceptedCAF(id) { delete rafIdMap[id]; }

  // Execute LLM code — pass intercepted RAF so Pause/Speed controls work
  if (cmd.code) {
    try {
      var setupFn = new Function('THREE', 'scene', 'camera', 'renderer', 'requestAnimationFrame', 'cancelAnimationFrame', cmd.code);
      setupFn(THREE, scene, camera, threeRenderer, interceptedRAF, interceptedCAF);
    } catch (e) {
      console.error('[Board] scene3d code error:', e);
      if (board.apiUrl) {
        fetch(board.apiUrl + '/api/fix-animation', {
          method: 'POST',
          headers: Object.assign({ 'Content-Type': 'application/json' }, board.getAuthHeaders ? board.getAuthHeaders() : {}),
          body: JSON.stringify({ code: cmd.code, error: e.message, type: 'threejs' }),
        }).then(function(r) { return r.ok ? r.json() : null; })
          .then(function(data) {
            if (!data || !data.code) return;
            try {
              var toRemove = [];
              scene.traverse(function(obj) {
                if (obj !== scene && obj !== camera && obj.type !== 'AmbientLight' && obj.type !== 'DirectionalLight') toRemove.push(obj);
              });
              toRemove.forEach(function(obj) { scene.remove(obj); });
              var fixedFn = new Function('THREE', 'scene', 'camera', 'renderer', 'requestAnimationFrame', 'cancelAnimationFrame', data.code);
              fixedFn(THREE, scene, camera, threeRenderer, interceptedRAF, interceptedCAF);
            } catch (e2) { console.error('[Board] scene3d fix also failed:', e2); }
          }).catch(function() {});
      }
    }
  }

  // Animation loop — drains LLM's pending RAFs + renders
  var animId;
  function animate(ts) {
    animId = requestAnimationFrame(animate);

    // Drain LLM's intercepted RAF callbacks
    if (pendingRAFs.length > 0) {
      var batch = pendingRAFs.slice(); pendingRAFs.length = 0;
      for (var i = 0; i < batch.length; i++) {
        var cb = rafIdMap[batch[i]]; delete rafIdMap[batch[i]];
        if (cb) { try { cb(ts); } catch (err) {} }
      }
    }

    if (controls) controls.update();

    // Smooth scale-up reveal for phase groups
    scene.traverse(function(obj) {
      if (obj._revealProgress !== undefined && obj._revealProgress < 1) {
        obj._revealProgress = Math.min(1, obj._revealProgress + 0.04);
        var t = obj._revealProgress;
        var ease = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
        obj.scale.setScalar(ease);
      }
    });

    threeRenderer.render(scene, camera);
  }
  animate(performance.now());

  // Store for cleanup + figure auto-sync
  board.animations.push({
    container: container,
    _threeScene: scene,
    instance: {
      remove: function() {
        cancelAnimationFrame(animId);
        pendingRAFs.length = 0;  // clear queued LLM callbacks
        for (var k in rafIdMap) delete rafIdMap[k];  // release closures
        try { threeRenderer.dispose(); } catch (e) {}
      },
      noLoop: function() { cancelAnimationFrame(animId); paused = true; }
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
  if (!fromEntry || !toEntry) {
    console.warn('[Board] connect: missing element — from="' + cmd.from + '" ' + (fromEntry ? '✓' : '✗') + ', to="' + cmd.to + '" ' + (toEntry ? '✓' : '✗') + '. Available ids:', Array.from(board.elements.keys()).join(', '));
    return;
  }
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

// LaTeX detection + KaTeX rendering
var _LATEX_RE = /\\(?:frac|left|right|hbar|alpha|beta|gamma|delta|lambda|omega|sigma|theta|pi|phi|psi|sqrt|sum|int|prod|lim|infty|partial|nabla|cdot|times|approx|equiv|neq|leq|geq|text|mathrm|mathbf|vec|hat|bar|dot|ddot|overline|underline|begin|end)\b|\^\{|\$\$/;

function _looksLikeLatex(text) {
  if (!text) return false;
  // Explicit $...$ or $$...$$ wrapping = always treat as LaTeX
  var t = text.trim();
  if (t.length > 2 && t[0] === '$' && t[t.length - 1] === '$') return true;
  // Backslash commands
  return _LATEX_RE.test(text);
}

// Heuristic: if the text has many English words (3+) without being wrapped
// in \text{}, it's mixed content and KaTeX will mash the words together as
// math variables. Auto-wrap the English runs in \text{}.
function _autoWrapTextRuns(latex) {
  // Skip if the text is already mostly LaTeX commands or already uses \text
  if (/\\text\s*\{/.test(latex)) return latex;
  // Match runs of 2+ consecutive ASCII words separated by spaces (English prose)
  // Don't touch math symbols, backslash commands, braces, parens
  return latex.replace(/\b([A-Za-z]{2,}(?:\s+[A-Za-z]{2,}){1,})\b/g, function(match) {
    // Don't wrap if the word looks like a LaTeX command name
    if (/^(?:frac|left|right|sqrt|sum|int|prod|lim|sin|cos|tan|log|ln|exp|min|max)$/.test(match)) {
      return match;
    }
    return '\\text{' + match + '}';
  });
}

function _tryKatex(el, latex) {
  if (typeof katex === 'undefined' || !latex) return false;
  if (!_looksLikeLatex(latex)) return false;
  try {
    var src = latex.trim();
    // Strip $$ ... $$ or $ ... $ delimiters — KaTeX expects bare LaTeX
    if (src.startsWith('$$') && src.endsWith('$$')) src = src.slice(2, -2).trim();
    else if (src.startsWith('$') && src.endsWith('$')) src = src.slice(1, -1).trim();
    var processed = _autoWrapTextRuns(src);
    katex.render(processed, el, { throwOnError: false, displayMode: true });
    return true;
  } catch (e) {
    console.warn('[Board] KaTeX render failed:', e.message);
    return false;
  }
}

async function renderText(cmd) {
  // ── Markdown-style code fences inside text ──
  // If the text contains ``` fences, split into prose + code segments.
  // Each prose segment animates char-by-char like normal text. Each code
  // segment renders as a read-only bd-code-block (like cmd:"code" without
  // the editor). The model can weave a code snippet into a sentence
  // without switching commands.
  var rawText = cmd.text || '';
  if (typeof rawText === 'string' && rawText.indexOf('```') !== -1) {
    var segments = _splitMarkdownFences(rawText);
    if (segments.length > 1) {
      // Mixed content. Place a wrapper, then animate prose / render code.
      var wrap = document.createElement('div');
      wrap.className = 'bd-el bd-text-mixed';
      if (cmd.id) { wrap.id = cmd.id; registerElement(cmd.id, wrap); }
      placeElement(wrap, cmd.placement, cmd);
      for (var i = 0; i < segments.length; i++) {
        var seg = segments[i];
        if (seg.kind === 'prose') {
          if (!seg.text.trim()) continue;
          var prose = document.createElement('div');
          prose.className = 'bd-text bd-text-segment ' + colorClass(cmd.color || 'white') + ' ' + sizeClass(cmd.size);
          wrap.appendChild(prose);
          if (!_tryKatex(prose, seg.text)) {
            await animateText(prose, seg.text, { charDelay: cmd.charDelay });
          }
        } else {
          // Code segment — render as a read-only bd-code-block
          var codeBlock = document.createElement('div');
          codeBlock.className = 'bd-el bd-code-block bd-text-code-segment';
          var hdr = document.createElement('div');
          hdr.className = 'bd-code-header';
          hdr.innerHTML = '<span class="bd-code-lang">' + escapeHtml((seg.lang || 'text').toUpperCase()) + '</span>';
          codeBlock.appendChild(hdr);
          var body = document.createElement('pre');
          body.className = 'bd-code-body';
          body.textContent = seg.text;
          codeBlock.appendChild(body);
          wrap.appendChild(codeBlock);
        }
      }
      return;
    }
  }

  var el = createStyledElement('div', cmd, 'bd-text');
  placeElement(el, cmd.placement, cmd);
  if (!_tryKatex(el, cmd.text)) {
    await animateText(el, cmd.text, { charDelay: cmd.charDelay });
  }
}

// Parse triple-backtick fences out of a markdown-ish string.
// Returns an array of segments: [{kind: 'prose'|'code', text, lang?}, ...]
// Tolerates literal "\\n" escapes and unmatched fences.
function _splitMarkdownFences(text) {
  // Normalize literal escape sequences (model often double-escapes \n)
  if (text.indexOf('\\') !== -1) {
    text = text.replace(/\\n/g, '\n').replace(/\\r/g, '\r').replace(/\\t/g, '\t');
  }
  var segments = [];
  var fenceRe = /```([a-zA-Z0-9_+-]*)\s*\n([\s\S]*?)```/g;
  var lastIndex = 0;
  var match;
  while ((match = fenceRe.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ kind: 'prose', text: text.slice(lastIndex, match.index) });
    }
    segments.push({ kind: 'code', lang: match[1] || 'text', text: match[2] });
    lastIndex = fenceRe.lastIndex;
  }
  if (lastIndex < text.length) {
    segments.push({ kind: 'prose', text: text.slice(lastIndex) });
  }
  return segments;
}

function renderGap(cmd) {
  var el = document.createElement('div');
  el.className = 'bd-el bd-gap';
  el.style.height = (cmd.height || 20) + 'px';
  if (cmd.id) el.id = cmd.id;
  placeElement(el, cmd.placement, cmd);
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
  if (!_tryKatex(text, cmd.text)) {
    await animateText(text, cmd.text, { charDelay: cmd.charDelay });
  }
}

async function renderCheckCross(cmd, isCheck) {
  var el = createElement('div', cmd, isCheck ? 'bd-check' : 'bd-cross');

  var text = document.createElement('span');
  text.className = 'bd-check-text ' + colorClass(cmd.color || 'white') + ' ' + sizeClass(cmd.size);
  el.appendChild(text);

  placeElement(el, cmd.placement, cmd);
  if (!_tryKatex(text, cmd.text)) {
    await animateText(text, cmd.text, { charDelay: cmd.charDelay || 25 });
  }
}

var _calloutVariantCounter = 0;
async function renderCallout(cmd) {
  // Callouts are PROSE. Strip x,y to prevent overlap.
  var safeCmd = cmd;
  if (typeof cmd.x === 'number' || typeof cmd.y === 'number') {
    safeCmd = Object.assign({}, cmd);
    delete safeCmd.x;
    delete safeCmd.y;
    if (!safeCmd.placement) safeCmd.placement = 'below';
  }

  var variant = safeCmd.variant || ((_calloutVariantCounter++ % 3) + 1);
  var el = createElement('div', safeCmd, 'bd-callout', colorClass(safeCmd.color || 'gold'));
  el.classList.add('bd-cv-' + variant);

  var text = document.createElement('div');
  text.className = 'bd-callout-text ' + sizeClass(safeCmd.size);
  el.appendChild(text);

  placeElement(el, safeCmd.placement, safeCmd);
  await animateText(text, safeCmd.text, { charDelay: safeCmd.charDelay });
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

// ═══════════════════════════════════════════════════════════════
// NEW BOARD BLOCKS — split, flow, diff, question
// Controlled layout components. The LLM picks WHAT to show,
// the renderer handles WHERE it goes. No x,y coordinates.
// ═══════════════════════════════════════════════════════════════

// ── SPLIT — thing left, meaning right ──────────────────────
// Used for: equation+explanation, term+definition, code+annotation
var _splitVariantCounter = 0;
async function renderSplit(cmd) {
  var variant = cmd.variant || ((_splitVariantCounter++ % 3) + 1);
  var el = createElement('div', cmd, 'bd-split', 'bd-sv-' + variant);
  if (cmd.size === 'lg') el.classList.add('bd-split-lg');
  if (cmd.size === 'sm') el.classList.add('bd-split-sm');

  var left = document.createElement('span');
  left.className = 'bd-split-l';
  if (cmd.leftColor) left.classList.add(colorClass(cmd.leftColor));
  el.appendChild(left);

  var right = document.createElement('span');
  right.className = 'bd-split-r';
  el.appendChild(right);

  placeElement(el, cmd.placement, cmd);

  // Left side: try KaTeX first (for proper fractions/symbols), fall back to animation
  if (!_tryKatex(left, cmd.left)) {
    await animateText(left, cmd.left || '', { charDelay: cmd.charDelay || 20 });
  }
  // Right side: always prose, just animate
  await animateText(right, cmd.right || '', { charDelay: cmd.charDelay || 18 });
}

// ── FLOW — process chain A → B → C ────────────────────────
// Created with first node(s). Grows via cmd:"flow-add".
function renderFlow(cmd) {
  var el = createElement('div', cmd, 'bd-flow');
  if (cmd.compact) el.classList.add('bd-flow-compact');

  var nodes = cmd.nodes || [];
  for (var i = 0; i < nodes.length; i++) {
    if (i > 0) {
      // Edge between previous node and this one
      var edge = document.createElement('div');
      edge.className = 'bd-flow-edge';
      edge.innerHTML = '<div class="bd-flow-line"></div>' +
        (nodes[i].edge ? '<div class="bd-flow-verb">' + escapeHtml(nodes[i].edge) + '</div>' : '');
      el.appendChild(edge);
    }
    el.appendChild(_createFlowNode(nodes[i]));
  }

  placeElement(el, cmd.placement, cmd);
}

function _createFlowNode(n) {
  var node = document.createElement('div');
  node.className = 'bd-flow-node';
  var color = n.color || '#eeeeec';
  node.innerHTML =
    '<div class="bd-flow-dot" style="background:' + color + ';box-shadow:0 0 12px ' + color + '"></div>' +
    '<div class="bd-flow-name" style="color:' + color + '">' + escapeHtml(n.name || '') + '</div>' +
    (n.sub ? '<div class="bd-flow-sub">' + escapeHtml(n.sub) + '</div>' : '');
  return node;
}

// cmd:"flow-add" — append one node+edge to an existing flow
function renderFlowAdd(cmd) {
  if (!cmd.target) return;
  var el = document.getElementById(cmd.target);
  if (!el || !el.classList.contains('bd-flow')) return;

  // Add edge
  var edge = document.createElement('div');
  edge.className = 'bd-flow-edge';
  edge.innerHTML = '<div class="bd-flow-line"></div>' +
    (cmd.edge ? '<div class="bd-flow-verb">' + escapeHtml(cmd.edge) + '</div>' : '');
  el.appendChild(edge);

  // Add node
  var node = cmd.node || {};
  el.appendChild(_createFlowNode(node));
}

// ── DIFF — before/after (fix mode) or side-by-side (compare mode) ──
async function renderDiff(cmd) {
  var mode = cmd.mode || 'fix';
  var el = createElement('div', cmd, 'bd-diff', 'bd-diff-' + mode);

  if (mode === 'compare') {
    // Compare mode — two equal-weight sides with items.
    // Items can be provided upfront OR added beat-by-beat via diff-add.
    var leftData = cmd.left || {};
    var rightData = cmd.right || {};
    var leftColor = leftData.color || '#53d8fb';
    var rightColor = rightData.color || '#fbbf24';

    var leftSide = document.createElement('div');
    leftSide.className = 'bd-diff-side';
    leftSide.dataset.color = leftColor;
    leftSide.innerHTML = '<div class="bd-diff-label" style="color:' + leftColor + '">' + escapeHtml(leftData.label || 'A') + '</div>';
    var leftItems = document.createElement('div');
    leftItems.className = 'bd-diff-items';
    leftSide.appendChild(leftItems);

    var bar = document.createElement('div');
    bar.className = 'bd-diff-bar';

    var rightSide = document.createElement('div');
    rightSide.className = 'bd-diff-side';
    rightSide.dataset.color = rightColor;
    rightSide.innerHTML = '<div class="bd-diff-label" style="color:' + rightColor + '">' + escapeHtml(rightData.label || 'B') + '</div>';
    var rightItems = document.createElement('div');
    rightItems.className = 'bd-diff-items';
    rightSide.appendChild(rightItems);

    // If items are provided upfront, add them (for non-beat-by-beat usage)
    (leftData.items || []).forEach(function(item) {
      _addDiffItem(leftItems, item, leftColor);
    });
    (rightData.items || []).forEach(function(item) {
      _addDiffItem(rightItems, item, rightColor);
    });

    el.appendChild(leftSide);
    el.appendChild(bar);
    el.appendChild(rightSide);
    placeElement(el, cmd.placement, cmd);
  } else {
    // Fix mode — left dimmed+struck, right bright
    var before = document.createElement('div');
    before.className = 'bd-diff-side bd-diff-before';
    before.innerHTML = '<div class="bd-diff-label">' + escapeHtml(cmd.beforeLabel || 'before') + '</div>';
    var beforeBody = document.createElement('div');
    beforeBody.className = 'bd-diff-body';
    before.appendChild(beforeBody);

    var bar = document.createElement('div');
    bar.className = 'bd-diff-bar';

    var after = document.createElement('div');
    after.className = 'bd-diff-side bd-diff-after';
    after.innerHTML = '<div class="bd-diff-label">' + escapeHtml(cmd.afterLabel || 'after') + '</div>';
    var afterBody = document.createElement('div');
    afterBody.className = 'bd-diff-body';
    after.appendChild(afterBody);

    el.appendChild(before);
    el.appendChild(bar);
    el.appendChild(after);
    placeElement(el, cmd.placement, cmd);

    // Animate before first (dims in), then after (types bright)
    await animateText(beforeBody, cmd.before || '', { charDelay: 15 });
    await animateText(afterBody, cmd.after || '', { charDelay: 18 });
  }

  // Optional note below
  if (cmd.note) {
    var note = document.createElement('div');
    note.className = 'bd-diff-note';
    el.appendChild(note);
    await animateText(note, cmd.note, { charDelay: 16 });
  }
}

function _addDiffItem(container, text, color) {
  var d = document.createElement('div');
  d.className = 'bd-diff-item bd-diff-item-enter';
  d.style.color = color;
  d.textContent = text;
  container.appendChild(d);
  // Trigger enter animation
  requestAnimationFrame(function() { d.classList.remove('bd-diff-item-enter'); });
  return d;
}

// cmd:"diff-add" — add one item to an existing diff compare component
function renderDiffAdd(cmd) {
  if (!cmd.target) return;
  var el = document.getElementById(cmd.target);
  if (!el || !el.classList.contains('bd-diff-compare')) {
    // Fallback: look for bd-diff
    el = document.getElementById(cmd.target);
    if (!el || !el.classList.contains('bd-diff')) return;
  }

  var sides = el.querySelectorAll('.bd-diff-side');
  if (sides.length < 2) return;

  var side = cmd.side === 'right' ? sides[1] : sides[0];
  var color = side.dataset.color || (cmd.side === 'right' ? '#fbbf24' : '#53d8fb');
  var items = side.querySelector('.bd-diff-items');
  if (!items) return;

  _addDiffItem(items, cmd.text || '', cmd.color || color);
}

// ── QUESTION — visually distinct from teaching, RANDOM style ───
// 4 visual variants picked randomly so the board doesn't feel templated
// when multiple questions appear in one session.
var _questionVariantCounter = 0;
async function renderQuestion(cmd) {
  var variant = cmd.style || ((_questionVariantCounter++ % 4) + 1);
  var el = createElement('div', cmd, 'bd-question-block', 'bd-qv-' + variant);

  if (cmd.context) {
    var ctx = document.createElement('div');
    ctx.className = 'bd-question-ctx';
    el.appendChild(ctx);
  }

  var text = document.createElement('div');
  text.className = 'bd-question-text';
  el.appendChild(text);

  if (cmd.hint) {
    var hint = document.createElement('div');
    hint.className = 'bd-question-hint';
    el.appendChild(hint);
  }

  placeElement(el, cmd.placement, cmd);

  if (cmd.context) await animateText(ctx, cmd.context, { charDelay: 16 });
  await animateText(text, cmd.text || '', { charDelay: 20 });
  if (cmd.hint) await animateText(hint, cmd.hint, { charDelay: 16 });
}

// ═══════════════════════════════════════════════════════════════

function renderStrikeout(cmd) {
  if (!cmd.target) return;
  var el = document.getElementById(cmd.target);
  if (el) el.classList.add('bd-strikeout');
}

async function renderUpdate(cmd) {
  if (!cmd.target) return;
  var el = document.getElementById(cmd.target);
  if (!el) return;

  // Normalize literal escape sequences (model often double-escapes \n)
  var text = cmd.text || '';
  if (typeof text === 'string' && text.indexOf('\\') !== -1) {
    text = text.replace(/\\n/g, '\n').replace(/\\r/g, '\r').replace(/\\t/g, '\t');
  }

  // ── Split special case ──
  // When targeting a split, update the left side (with KaTeX) and
  // optionally the right side. This lets the model build an equation
  // piece by piece across beats: each beat extends the left (growing
  // equation) and changes the right (new annotation for this piece).
  if (el.classList.contains('bd-split')) {
    // Scroll the split into view — same reason as code blocks
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });

    var leftEl = el.querySelector('.bd-split-l');
    var rightEl = el.querySelector('.bd-split-r');
    // cmd.left or cmd.text updates the left side
    var newLeft = cmd.left || text;
    if (leftEl && newLeft) {
      leftEl.textContent = '';
      leftEl.classList.remove('hljs');
      if (!_tryKatex(leftEl, newLeft)) {
        await animateText(leftEl, newLeft, { charDelay: cmd.charDelay || 18 });
      }
    }
    // cmd.right updates the right side (optional — keeps old if not provided)
    if (rightEl && cmd.right !== undefined) {
      rightEl.textContent = '';
      await animateText(rightEl, cmd.right, { charDelay: cmd.charDelay || 16 });
    }
    return;
  }

  // ── Code block special case ──
  // Code blocks have structure: header / body / tests / output. The naive
  // textContent='' wipes the whole structure. Instead, update only the
  // body element's text. AND — if the new text is a SUPERSET of the old
  // (model is growing the code line by line across beats), animate only
  // the new suffix so existing lines stay put. The student watches the
  // code grow in place, beat by beat, just like text/equation/step do.
  if (el.classList.contains('bd-code-block')) {
    // Scroll the code block into view BEFORE animating — the tutor might
    // be updating a code block that scrolled off-screen while other content
    // was added below it. The student needs to SEE the code changing.
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });

    var body = el.querySelector('.bd-code-body');
    if (body) {
      // Use dataset.rawText for the existing text comparison — this is
      // the authoritative source with proper \n. body.textContent loses
      // newlines because animateText converts \n→<br> and textContent
      // doesn't translate <br> back. If rawText isn't set (legacy),
      // fall back to textContent.
      var existing = body.dataset.rawText || body.textContent || '';
      var charDelay = cmd.charDelay !== undefined ? cmd.charDelay : 20;

      // Flatten any highlight markup before appending so the new chars
      // land as plain text. We re-highlight the whole body once done.
      if (body.classList.contains('hljs')) {
        body.textContent = existing;
        body.classList.remove('hljs');
      }

      if (text.length > existing.length && text.indexOf(existing) === 0) {
        // GROW: append-only update. Use _animateAppend (NOT animateText)
        // because animateText clobbers parentEl at the end of its run.
        // Previous lines stay put — only the new suffix types in.
        var suffix = text.slice(existing.length);
        await _animateAppend(body, suffix, { charDelay: charDelay });
      } else if (text === existing) {
        // No change — nothing to do.
      } else {
        // REPLACE: full rewrite (refactor / fix-up). Clear and retype.
        body.textContent = '';
        await animateText(body, text, { charDelay: charDelay });
      }

      // Update the authoritative raw text for future diffs + highlights.
      body.dataset.rawText = text;

      // Re-highlight from the raw text (not from DOM textContent).
      var entry = board.codeRunners && board.codeRunners[cmd.target];
      var lang = entry ? entry.lang : null;
      _highlightCodeBody(body, lang);

      // Re-wrap lines with line numbers + optional highlight.
      _wrapCodeLines(body, cmd.highlight);

      if (entry) {
        entry.originalCode = text;
        entry.currentCode = text;
        entry.lastInteractedAt = Date.now();
        // A code update from the tutor invalidates the previous run output
        // (the code changed) — clear the visible panels and the registry.
        entry.lastRun = null;
        if (entry.tests) entry.tests.results = null;
        _resetCodeRunnerPanels(el);
      }
      return;
    }
  }

  el.textContent = '';
  if (cmd.color) {
    el.className = el.className.replace(/bd-chalk-\w+/g, '');
    el.classList.add(colorClass(cmd.color));
  }
  await animateText(el, text, { charDelay: 20 });
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
