/**
 * Compound Command Renderers — create DOM elements for each command type.
 * Each function returns an HTMLElement (or appends children to a container).
 */

import { createElement, createStyledElement, colorClass, sizeClass } from './renderer.js';
import { animateText } from './text-animator.js';
import { placeElement } from './placement.js';
import { board } from './state.js';

/**
 * Process a single draw command — routes to the appropriate renderer.
 * @param {Object} cmd - Draw command JSON
 */
export async function runCommand(cmd) {
  if (board.cancelFlag) return;
  if (!board.liveScene) return;

  // Default placement
  const contentCmds = ['text', 'latex', 'animation', 'figure', 'equation', 'step',
    'check', 'cross', 'callout', 'list', 'divider'];
  if (!cmd.placement && contentCmds.includes(cmd.cmd)) {
    cmd.placement = 'below';
  }

  switch (cmd.cmd) {
    case 'text':     await renderText(cmd); break;
    case 'h1':       await renderText({ ...cmd, size: 'h1' }); break;
    case 'h2':       await renderText({ ...cmd, size: 'h2' }); break;
    case 'h3':       await renderText({ ...cmd, size: 'h3' }); break;
    case 'gap':      renderGap(cmd); break;
    case 'note':     await renderText({ ...cmd, size: 'small', color: cmd.color || 'dim' }); break;
    case 'latex':    await renderEquation(cmd); break;
    case 'equation': await renderEquation(cmd); break;
    case 'step':     await renderStep(cmd); break;
    case 'check':    await renderCheckCross(cmd, true); break;
    case 'cross':    await renderCheckCross(cmd, false); break;
    case 'callout':  await renderCallout(cmd); break;
    case 'list':     await renderList(cmd); break;
    case 'divider':  renderDivider(cmd); break;
    case 'animation': await renderAnimation(cmd); break;
    case 'figure':   await renderFigure(cmd); break;
    case 'narrate':  await renderNarrate(cmd); break;
    case 'columns':  renderColumns(cmd); break;
    case 'columns-end': renderColumnsEnd(); break;
    case 'annotate': renderAnnotate(cmd); break;
    case 'strikeout': renderStrikeout(cmd); break;
    case 'update':   await renderUpdate(cmd); break;
    case 'delete':   renderDelete(cmd); break;
    case 'clone':    await renderClone(cmd); break;
    case 'clear':    clearBoard(); break;
    default:
      console.warn('[Board] Unknown command:', cmd.cmd);
  }

  // Auto-scroll to keep new content visible
  autoScroll();
}

// ── TEXT ──────────────────────────────────────────────

async function renderText(cmd) {
  const el = createStyledElement('div', cmd, 'bd-text');
  placeElement(el, cmd.placement, cmd);
  if (!_tryKatex(el, cmd.text)) {
    await animateText(el, cmd.text, { charDelay: cmd.charDelay });
  }
}

// ── EQUATION ─────────────────────────────────────────

const _LATEX_RE = /\\(?:frac|left|right|hbar|alpha|beta|gamma|delta|lambda|omega|sigma|theta|pi|phi|psi|sqrt|sum|int|prod|lim|infty|partial|nabla|cdot|times|approx|equiv|neq|leq|geq|text|mathrm|mathbf|vec|hat|bar|dot|ddot|overline|underline|begin|end)\b|\\[{()}[\]]|\^\{|\$\$/;

function _looksLikeLatex(text) {
  return text && _LATEX_RE.test(text);
}

// Heuristic: if the text has runs of English words not wrapped in \text{},
// auto-wrap them so KaTeX doesn't mash them into italic math letters.
function _autoWrapTextRuns(latex) {
  if (/\\text\s*\{/.test(latex)) return latex;
  return latex.replace(/\b([A-Za-z]{2,}(?:\s+[A-Za-z]{2,}){1,})\b/g, function(match) {
    if (/^(?:frac|left|right|sqrt|sum|int|prod|lim|sin|cos|tan|log|ln|exp|min|max)$/.test(match)) {
      return match;
    }
    return '\\text{' + match + '}';
  });
}

function _tryKatex(el, latex) {
  /** Render LaTeX into el via KaTeX. Returns true if successful. */
  if (typeof katex === 'undefined' || !latex) return false;
  // Only attempt if it looks like LaTeX
  if (!_looksLikeLatex(latex)) return false;
  try {
    const processed = _autoWrapTextRuns(latex);
    katex.render(processed, el, { throwOnError: false, displayMode: true });
    return true;
  } catch (e) {
    console.warn('[Board] KaTeX render failed:', e.message);
    return false;
  }
}

async function renderEquation(cmd) {
  const el = createElement('div', cmd, 'bd-equation');
  el.classList.add(colorClass(cmd.color));

  const main = document.createElement('span');
  main.className = `bd-eq-main ${sizeClass(cmd.size)}`;
  el.appendChild(main);

  if (cmd.note) {
    const note = document.createElement('span');
    note.className = `bd-eq-note bd-chalk-dim ${sizeClass('small')}`;
    note.textContent = cmd.note;
    el.appendChild(note);
  }

  placeElement(el, cmd.placement, cmd);

  // Try KaTeX first, fall back to character animation for plain text
  if (!_tryKatex(main, cmd.text)) {
    await animateText(main, cmd.text, { charDelay: cmd.charDelay });
  }
}

// ── STEP ─────────────────────────────────────────────

async function renderStep(cmd) {
  const el = createElement('div', cmd, 'bd-step', colorClass(cmd.color || 'cyan'));

  const num = document.createElement('span');
  num.className = 'bd-step-num';
  num.textContent = String(cmd.n || 1);
  el.appendChild(num);

  const text = document.createElement('span');
  text.className = `bd-step-text ${sizeClass(cmd.size)}`;
  el.appendChild(text);

  placeElement(el, cmd.placement, cmd);
  if (!_tryKatex(text, cmd.text)) {
    await animateText(text, cmd.text, { charDelay: cmd.charDelay });
  }
}

// ── CHECK / CROSS ────────────────────────────────────

async function renderCheckCross(cmd, isCheck) {
  const el = createElement('div', cmd, isCheck ? 'bd-check' : 'bd-cross');

  const text = document.createElement('span');
  text.className = `bd-check-text ${colorClass(cmd.color || 'white')} ${sizeClass(cmd.size)}`;
  el.appendChild(text);

  placeElement(el, cmd.placement, cmd);
  await animateText(text, cmd.text, { charDelay: cmd.charDelay || 25 });
}

// ── CALLOUT ──────────────────────────────────────────

async function renderCallout(cmd) {
  const el = createElement('div', cmd, 'bd-callout', colorClass(cmd.color || 'gold'));

  const text = document.createElement('div');
  text.className = `bd-callout-text ${sizeClass(cmd.size)}`;
  el.appendChild(text);

  placeElement(el, cmd.placement, cmd);
  if (!_tryKatex(text, cmd.text)) {
    await animateText(text, cmd.text, { charDelay: cmd.charDelay });
  }
}

// ── LIST ─────────────────────────────────────────────

async function renderList(cmd) {
  const el = createElement('div', cmd, 'bd-list', colorClass(cmd.color || 'white'));
  el.dataset.style = cmd.style || 'bullet';

  const items = cmd.items || [];
  for (const item of items) {
    const li = document.createElement('div');
    li.className = `bd-list-item ${sizeClass(cmd.size)}`;
    el.appendChild(li);
    // Text will be set after placement
  }

  placeElement(el, cmd.placement, cmd);

  // Animate items sequentially
  const listItems = el.querySelectorAll('.bd-list-item');
  for (let i = 0; i < items.length && i < listItems.length; i++) {
    if (board.cancelFlag) break;
    await animateText(listItems[i], items[i], { charDelay: 25 });
  }
}

// ── GAP (vertical spacing) ───────────────────────────

function renderGap(cmd) {
  const el = document.createElement('div');
  el.className = 'bd-el bd-gap';
  el.style.height = (cmd.height || 20) + 'px';
  if (cmd.id) el.id = cmd.id;
  placeElement(el, cmd.placement, cmd);
}

// ── DIVIDER ──────────────────────────────────────────

function renderDivider(cmd) {
  const el = document.createElement('hr');
  el.className = 'bd-el bd-divider';
  if (cmd.id) el.id = cmd.id;
  placeElement(el, cmd.placement, cmd);
}

// ── COLUMNS (grid layout zone) ───────────────────────

function renderColumns(cmd) {
  const scene = board.liveScene;
  if (!scene) return;
  board.currentRow = null;

  const cols = cmd.cols || 2;
  const grid = document.createElement('div');
  grid.className = 'bd-el bd-columns';
  grid.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
  if (cmd.id) grid.id = cmd.id;
  scene.appendChild(grid);
  board.currentColumns = grid;
}

function renderColumnsEnd() {
  board.currentColumns = null;
}

// ── ANNOTATE (relative label on existing element) ────

function renderAnnotate(cmd) {
  if (!cmd.target || !cmd.text) return;
  const target = document.getElementById(cmd.target) || (board.elements.get(cmd.target) || {}).element;
  if (!target) {
    // Fallback: render as dim text
    const el = createStyledElement('div', { ...cmd, color: cmd.color || 'dim', size: 'small' }, 'bd-text');
    placeElement(el, 'below', cmd);
    animateText(el, cmd.text, { charDelay: 20 });
    return;
  }

  const ann = document.createElement('span');
  ann.className = `bd-annotation bd-chalk-${cmd.color || 'dim'}`;
  ann.textContent = cmd.text;

  const pos = cmd.pos || 'right';
  ann.classList.add(`bd-ann-${pos}`);

  if (pos === 'right' || pos === 'beside') {
    const row = target.closest('.bd-row');
    if (row) {
      row.appendChild(ann);
    } else {
      const newRow = document.createElement('div');
      newRow.className = 'bd-row';
      target.parentNode.insertBefore(newRow, target);
      newRow.appendChild(target);
      newRow.appendChild(ann);
    }
  } else {
    const wrapper = target.closest('.bd-row') || target;
    if (wrapper.nextSibling) {
      wrapper.parentNode.insertBefore(ann, wrapper.nextSibling);
    } else {
      wrapper.parentNode.appendChild(ann);
    }
  }
}

// ── ANIMATION ────────────────────────────────────────

async function renderAnimation(cmd) {
  // Lazy import to avoid circular deps
  const { createAnimation } = await import('./animation.js');
  await createAnimation(cmd);
}

// ── FIGURE (animation + narration column) ───────────
//
// Creates a row holding the animation on the left and an empty narration
// column on the right. Subsequent cmd:"narrate" commands with target=<id>
// append one line at a time into the narration column, animated.

async function renderFigure(cmd) {
  if (!cmd.id) {
    console.warn('[Board] cmd:figure requires an id so cmd:narrate can target it');
    cmd.id = 'fig-' + Math.random().toString(36).slice(2, 8);
  }

  const wrapper = document.createElement('div');
  wrapper.className = 'bd-el bd-figure';
  wrapper.id = cmd.id;
  wrapper.dataset.cmd = 'figure';

  const animSlot = document.createElement('div');
  animSlot.className = 'bd-figure-anim';
  wrapper.appendChild(animSlot);

  const narration = document.createElement('div');
  narration.className = 'bd-figure-narration';
  if (cmd.title) {
    const head = document.createElement('div');
    head.className = 'bd-figure-narration-title';
    head.textContent = cmd.title;
    narration.appendChild(head);
  }
  wrapper.appendChild(narration);

  placeElement(wrapper, cmd.placement || 'below', cmd);

  // Inject the animation into the left slot. createAnimation calls
  // placeElement(figure, cmd.placement, cmd) which writes into board.liveScene,
  // so we temporarily swap liveScene to the anim slot.
  const { createAnimation } = await import('./animation.js');
  const savedScene = board.liveScene;
  board.liveScene = animSlot;
  try {
    const animCmd = { ...cmd, id: cmd.id + '-anim', placement: 'below' };
    await createAnimation(animCmd);
  } finally {
    board.liveScene = savedScene;
  }
}

// cmd:"narrate" is a convenience alias for cmd:"text" + placement="figure:<target>".
// It exists so older prompts and the figure pattern doc still work.
async function renderNarrate(cmd) {
  if (!cmd.target || !cmd.text) return;
  await renderText({ ...cmd, placement: `figure:${cmd.target}`, target: undefined });
}

// ── EDITING COMMANDS ─────────────────────────────────

function renderStrikeout(cmd) {
  if (!cmd.target) return;
  const el = document.getElementById(cmd.target);
  if (el) el.classList.add('bd-strikeout');
}

async function renderUpdate(cmd) {
  if (!cmd.target || !cmd.text) return;
  const el = document.getElementById(cmd.target);
  if (!el) return;
  // Clear old content
  el.textContent = '';
  // Update color if specified
  if (cmd.color) {
    el.className = el.className.replace(/bd-chalk-\w+/g, '');
    el.classList.add(colorClass(cmd.color));
  }
  await animateText(el, cmd.text, { charDelay: 20 });
}

function renderDelete(cmd) {
  if (!cmd.target) return;
  const el = document.getElementById(cmd.target);
  if (el) el.classList.add('bd-deleted');
}

async function renderClone(cmd) {
  if (!cmd.source) return;
  const source = document.getElementById(cmd.source);
  if (!source) return;
  const clone = source.cloneNode(true);
  clone.id = cmd.id || `${cmd.source}-copy`;
  clone.classList.remove('bd-strikeout', 'bd-deleted', 'bd-highlight');
  placeElement(clone, cmd.placement || 'below', cmd);
}

// ── BOARD CLEAR ──────────────────────────────────────

function clearBoard() {
  const { clearAll } = require('./scene.js');
  clearAll();
}

// ── AUTO-SCROLL ──────────────────────────────────────

function autoScroll() {
  const wrap = document.getElementById('bd-canvas-wrap');
  if (!wrap || !board.liveScene) return;

  const lastEl = board.liveScene.lastElementChild;
  if (!lastEl || lastEl.classList.contains('bd-grid-bg')) return;

  // Only scroll if the new element is below the viewport
  const wrapRect = wrap.getBoundingClientRect();
  const elRect = lastEl.getBoundingClientRect();

  if (elRect.bottom > wrapRect.bottom - 20) {
    lastEl.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }
}
