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
    case 'latex':    await renderText(cmd); break; // LaTeX→Unicode already done upstream
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
  await animateText(el, cmd.text, { charDelay: cmd.charDelay });
}

// ── EQUATION ─────────────────────────────────────────

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
  await animateText(main, cmd.text, { charDelay: cmd.charDelay });
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
  await animateText(text, cmd.text, { charDelay: cmd.charDelay });
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
  await animateText(text, cmd.text, { charDelay: cmd.charDelay });
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
  await animateText(text, cmd.text, { charDelay: cmd.charDelay });
}

// ── ANIMATION ────────────────────────────────────────
// Imported from animation.js — just re-export the router entry point

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
