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
  const contentCmds = ['text', 'latex', 'animation', 'equation', 'compare', 'step',
    'check', 'cross', 'callout', 'list', 'divider', 'result'];
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
    case 'compare':  await renderCompare(cmd); break;
    case 'step':     await renderStep(cmd); break;
    case 'check':    await renderCheckCross(cmd, true); break;
    case 'cross':    await renderCheckCross(cmd, false); break;
    case 'callout':  await renderCallout(cmd); break;
    case 'list':     await renderList(cmd); break;
    case 'divider':  renderDivider(cmd); break;
    case 'result':   await renderResult(cmd); break;
    case 'animation': await renderAnimation(cmd); break;
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

function _tryKatex(el, latex) {
  /** Render LaTeX into el via KaTeX. Returns true if successful. */
  if (typeof katex === 'undefined' || !latex) return false;
  // Only attempt if it looks like LaTeX
  if (!_looksLikeLatex(latex)) return false;
  try {
    katex.render(latex, el, { throwOnError: false, displayMode: true });
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

// ── COMPARE ──────────────────────────────────────────

async function renderCompare(cmd) {
  const el = createElement('div', cmd, 'bd-compare');
  const left = cmd.left || {};
  const right = cmd.right || {};

  // Left column
  const leftCol = document.createElement('div');
  leftCol.className = `bd-compare-col ${colorClass(left.color)}`;
  if (left.title) {
    const h = document.createElement('div');
    h.className = `bd-compare-col-label ${sizeClass('h2')}`;
    h.textContent = left.title;
    leftCol.appendChild(h);
  }
  (left.items || []).forEach(item => {
    const li = document.createElement('div');
    li.className = `bd-compare-item ${sizeClass('text')}`;
    li.textContent = `• ${item}`;
    leftCol.appendChild(li);
  });

  // Separator
  const sep = document.createElement('div');
  sep.className = 'bd-compare-sep';

  // Right column
  const rightCol = document.createElement('div');
  rightCol.className = `bd-compare-col ${colorClass(right.color)}`;
  if (right.title) {
    const h = document.createElement('div');
    h.className = `bd-compare-col-label ${sizeClass('h2')}`;
    h.textContent = right.title;
    rightCol.appendChild(h);
  }
  (right.items || []).forEach(item => {
    const li = document.createElement('div');
    li.className = `bd-compare-item ${sizeClass('text')}`;
    li.textContent = `• ${item}`;
    rightCol.appendChild(li);
  });

  el.appendChild(leftCol);
  el.appendChild(sep);
  el.appendChild(rightCol);

  placeElement(el, cmd.placement, cmd);
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

// ── RESULT ───────────────────────────────────────────

async function renderResult(cmd) {
  const el = createElement('div', cmd, 'bd-result', colorClass(cmd.color || 'gold'));

  if (cmd.label) {
    const label = document.createElement('span');
    label.className = 'bd-result-label';
    label.textContent = cmd.label;
    el.appendChild(label);
  }

  const text = document.createElement('span');
  text.className = `bd-result-text ${sizeClass(cmd.size)}`;
  el.appendChild(text);

  if (cmd.note) {
    const note = document.createElement('span');
    note.className = `bd-result-note bd-chalk-dim ${sizeClass('small')}`;
    note.textContent = `← ${cmd.note}`;
    el.appendChild(note);
  }

  placeElement(el, cmd.placement, cmd);
  // Result text is often LaTeX — try KaTeX first
  if (!_tryKatex(text, cmd.text)) {
    await animateText(text, cmd.text, { charDelay: cmd.charDelay });
  }
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
