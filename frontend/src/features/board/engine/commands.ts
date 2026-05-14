/**
 * Compound command renderers — create DOM elements per command type.
 * Native TypeScript port of frontend-legacy/board/commands.js, extended
 * with native React-friendly versions of the larger command types
 * (animation, scene3d, mermaid, chart, ds, code, assess-*).
 */

import {
  createElement,
  createStyledElement,
  colorClass,
  sizeClass,
} from './renderer';
import { animateText } from './text-animator';
import { placeElement } from './placement';
import { board, type BoardCommand } from './state';
import { clearAll } from './scene';

const CONTENT_CMDS = new Set([
  'text',
  'latex',
  'animation',
  'figure',
  'equation',
  'step',
  'check',
  'cross',
  'callout',
  'list',
  'divider',
]);

export async function runCommand(cmd: BoardCommand): Promise<void> {
  if (board.cancelFlag) return;
  if (!board.liveScene) return;

  if (!cmd.placement && CONTENT_CMDS.has(cmd.cmd)) {
    cmd.placement = 'below';
  }

  switch (cmd.cmd) {
    case 'text':
      await renderText(cmd);
      break;
    case 'h1':
      await renderText({ ...cmd, size: 'h1' });
      break;
    case 'h2':
      await renderText({ ...cmd, size: 'h2' });
      break;
    case 'h3':
      await renderText({ ...cmd, size: 'h3' });
      break;
    case 'gap':
      renderGap(cmd);
      break;
    case 'note':
      await renderText({ ...cmd, size: 'small', color: cmd.color ?? 'dim' });
      break;
    case 'latex':
    case 'equation':
      await renderEquation(cmd);
      break;
    case 'step':
      await renderStep(cmd);
      break;
    case 'check':
      await renderCheckCross(cmd, true);
      break;
    case 'cross':
      await renderCheckCross(cmd, false);
      break;
    case 'callout':
      await renderCallout(cmd);
      break;
    case 'list':
      await renderList(cmd);
      break;
    case 'divider':
      renderDivider(cmd);
      break;
    case 'animation':
      await renderAnimation(cmd);
      break;
    case 'figure':
      await renderFigure(cmd);
      break;
    case 'narrate':
      // Legacy parity: narrate requires both `target` and `text` — silently skip
      // otherwise instead of producing a broken `figure:` placement.
      if (cmd.target && cmd.text) {
        await renderText({ ...cmd, placement: `figure:${cmd.target}` });
      }
      break;
    case 'columns':
      renderColumns(cmd);
      break;
    case 'columns-end':
      board.currentColumns = null;
      break;
    case 'annotate':
      renderAnnotate(cmd);
      break;
    case 'strikeout':
      renderStrikeout(cmd);
      break;
    case 'update':
      await renderUpdate(cmd);
      break;
    case 'delete':
      renderDelete(cmd);
      break;
    case 'clone':
      await renderClone(cmd);
      break;
    case 'clear':
      clearAll();
      break;
    case 'mermaid':
      await renderMermaid(cmd);
      break;
    case 'chart':
      await renderChart(cmd);
      break;
    case 'scene3d':
      await renderScene3d(cmd);
      break;
    case 'code':
      await renderCode(cmd);
      break;
    case 'ds':
      await renderDataStructure(cmd);
      break;
    case 'tree':
    case 'array':
    case 'linked-list':
    case 'hash-map':
    case 'stack':
    case 'queue':
    case 'grid':
    case 'graph':
    case 'matrix':
      await renderDataStructure({ ...cmd, type: cmd.type ?? cmd.cmd, cmd: 'ds' });
      break;
    case 'diagram':
      await renderDiagram(cmd);
      break;
    case 'assess-mcq':
    case 'assess-freetext':
    case 'assess-spot-error':
    case 'assess-teachback':
    case 'assess-confidence':
      await renderAssessment(cmd);
      break;
    default:
      // eslint-disable-next-line no-console
      console.warn('[Board] Unknown command:', cmd.cmd);
  }

  autoScroll();
}

const LATEX_RE =
  /\\(?:frac|left|right|hbar|alpha|beta|gamma|delta|lambda|omega|sigma|theta|pi|phi|psi|sqrt|sum|int|prod|lim|infty|partial|nabla|cdot|times|approx|equiv|neq|leq|geq|text|mathrm|mathbf|vec|hat|bar|dot|ddot|overline|underline|begin|end)\b|\\[{()}[\]]|\^\{|\$\$/;

function looksLikeLatex(text: string | undefined): boolean {
  return !!text && LATEX_RE.test(text);
}

function autoWrapTextRuns(latex: string): string {
  if (/\\text\s*\{/.test(latex)) return latex;
  return latex.replace(/\b([A-Za-z]{2,}(?:\s+[A-Za-z]{2,}){1,})\b/g, (match) => {
    if (
      /^(?:frac|left|right|sqrt|sum|int|prod|lim|sin|cos|tan|log|ln|exp|min|max)$/.test(
        match,
      )
    ) {
      return match;
    }
    return '\\text{' + match + '}';
  });
}

async function tryKatex(el: HTMLElement, latex: string | undefined): Promise<boolean> {
  if (!latex || !looksLikeLatex(latex)) return false;
  try {
    const katex = (await import('katex')).default;
    const processed = autoWrapTextRuns(latex);
    katex.render(processed, el, { throwOnError: false, displayMode: true });
    return true;
  } catch {
    return false;
  }
}

async function renderText(cmd: BoardCommand): Promise<void> {
  const el = createStyledElement('div', cmd, 'bd-text');
  placeElement(el, cmd.placement, cmd);
  if (!(await tryKatex(el, cmd.text))) {
    await animateText(el, cmd.text, { charDelay: cmd.charDelay });
  }
}

async function renderEquation(cmd: BoardCommand): Promise<void> {
  const el = createElement('div', cmd, 'bd-equation', colorClass(cmd.color));
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
  if (!(await tryKatex(main, cmd.text))) {
    await animateText(main, cmd.text, { charDelay: cmd.charDelay });
  }
}

async function renderStep(cmd: BoardCommand): Promise<void> {
  const el = createElement('div', cmd, 'bd-step', colorClass(cmd.color ?? 'cyan'));
  const num = document.createElement('span');
  num.className = 'bd-step-num';
  num.textContent = String(cmd.n ?? 1);
  el.appendChild(num);
  const text = document.createElement('span');
  text.className = `bd-step-text ${sizeClass(cmd.size)}`;
  el.appendChild(text);
  placeElement(el, cmd.placement, cmd);
  if (!(await tryKatex(text, cmd.text))) {
    await animateText(text, cmd.text, { charDelay: cmd.charDelay });
  }
}

async function renderCheckCross(cmd: BoardCommand, isCheck: boolean): Promise<void> {
  const el = createElement('div', cmd, isCheck ? 'bd-check' : 'bd-cross');
  const text = document.createElement('span');
  text.className = `bd-check-text ${colorClass(cmd.color ?? 'white')} ${sizeClass(cmd.size)}`;
  el.appendChild(text);
  placeElement(el, cmd.placement, cmd);
  await animateText(text, cmd.text, { charDelay: cmd.charDelay ?? 25 });
}

async function renderCallout(cmd: BoardCommand): Promise<void> {
  const el = createElement('div', cmd, 'bd-callout', colorClass(cmd.color ?? 'gold'));
  const text = document.createElement('div');
  text.className = `bd-callout-text ${sizeClass(cmd.size)}`;
  el.appendChild(text);
  placeElement(el, cmd.placement, cmd);
  if (!(await tryKatex(text, cmd.text))) {
    await animateText(text, cmd.text, { charDelay: cmd.charDelay });
  }
}

async function renderList(cmd: BoardCommand): Promise<void> {
  const el = createElement('div', cmd, 'bd-list', colorClass(cmd.color ?? 'white'));
  el.dataset.style = cmd.style ?? 'bullet';
  const items = cmd.items ?? [];
  for (const _ of items) {
    const li = document.createElement('div');
    li.className = `bd-list-item ${sizeClass(cmd.size)}`;
    el.appendChild(li);
  }
  placeElement(el, cmd.placement, cmd);
  const listItems = el.querySelectorAll<HTMLElement>('.bd-list-item');
  for (let i = 0; i < items.length && i < listItems.length; i++) {
    if (board.cancelFlag) break;
    await animateText(listItems[i], items[i], { charDelay: 25 });
  }
}

function renderGap(cmd: BoardCommand): void {
  const el = document.createElement('div');
  el.className = 'bd-el bd-gap';
  el.style.height = (cmd.height ?? 20) + 'px';
  if (cmd.id) el.id = cmd.id;
  placeElement(el, cmd.placement, cmd);
}

function renderDivider(cmd: BoardCommand): void {
  const el = document.createElement('hr');
  el.className = 'bd-el bd-divider';
  if (cmd.id) el.id = cmd.id;
  placeElement(el, cmd.placement, cmd);
}

function renderColumns(cmd: BoardCommand): void {
  const scene = board.liveScene;
  if (!scene) return;
  board.currentRow = null;
  const cols = cmd.cols ?? 2;
  const grid = document.createElement('div');
  grid.className = 'bd-el bd-columns';
  grid.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
  if (cmd.id) grid.id = cmd.id;
  scene.appendChild(grid);
  board.currentColumns = grid;
}

function renderAnnotate(cmd: BoardCommand): void {
  if (!cmd.target || !cmd.text) return;
  const target =
    document.getElementById(cmd.target) ??
    board.elements.get(cmd.target)?.element ??
    null;
  if (!target) {
    const el = createStyledElement(
      'div',
      { ...cmd, color: cmd.color ?? 'dim', size: 'small' },
      'bd-text',
    );
    placeElement(el, 'below', cmd);
    void animateText(el, cmd.text, { charDelay: 20 });
    return;
  }
  const ann = document.createElement('span');
  ann.className = `bd-annotation bd-chalk-${cmd.color ?? 'dim'}`;
  ann.textContent = cmd.text;
  const pos = cmd.pos ?? 'right';
  ann.classList.add(`bd-ann-${pos}`);
  if (pos === 'right' || pos === 'beside') {
    const row = target.closest('.bd-row') as HTMLElement | null;
    if (row) {
      row.appendChild(ann);
    } else {
      const newRow = document.createElement('div');
      newRow.className = 'bd-row';
      target.parentNode?.insertBefore(newRow, target);
      newRow.appendChild(target);
      newRow.appendChild(ann);
    }
  } else {
    const wrapper = (target.closest('.bd-row') as HTMLElement | null) ?? target;
    if (wrapper.nextSibling) {
      wrapper.parentNode?.insertBefore(ann, wrapper.nextSibling);
    } else {
      wrapper.parentNode?.appendChild(ann);
    }
  }
}

function renderStrikeout(cmd: BoardCommand): void {
  if (!cmd.target) return;
  document.getElementById(cmd.target)?.classList.add('bd-strikeout');
}

async function renderUpdate(cmd: BoardCommand): Promise<void> {
  if (!cmd.target) return;
  const el =
    document.getElementById(cmd.target) ??
    board.elements.get(cmd.target)?.element ??
    null;
  if (!el) return;
  // If the target is a data-structure container, re-render it via the ds helper
  // so structural updates (cell values, pointers, highlights) work.
  if (el.classList.contains('bd-ds')) {
    try {
      const { updateDsCommand } = await import('../commands/ds');
      await updateDsCommand(el, cmd);
      return;
    } catch {
      /* fall through to text update */
    }
  }
  if (cmd.color) {
    el.className = el.className.replace(/bd-chalk-\w+/g, '');
    el.classList.add(colorClass(cmd.color));
  }
  if (cmd.text !== undefined) {
    el.textContent = '';
    await animateText(el, cmd.text, { charDelay: 20 });
  }
}

function renderDelete(cmd: BoardCommand): void {
  if (!cmd.target) return;
  document.getElementById(cmd.target)?.classList.add('bd-deleted');
}

async function renderClone(cmd: BoardCommand): Promise<void> {
  if (!cmd.source) return;
  const source = document.getElementById(cmd.source);
  if (!source) return;
  const clone = source.cloneNode(true) as HTMLElement;
  clone.id = cmd.id ?? `${cmd.source}-copy`;
  clone.classList.remove('bd-strikeout', 'bd-deleted', 'bd-highlight');
  placeElement(clone, cmd.placement ?? 'below', cmd);
}

async function renderAnimation(cmd: BoardCommand): Promise<void> {
  const { createAnimation } = await import('../commands/animation');
  await createAnimation(cmd);
}

async function renderFigure(cmd: BoardCommand): Promise<void> {
  if (!cmd.id) {
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
  if (typeof cmd.title === 'string') {
    const head = document.createElement('div');
    head.className = 'bd-figure-narration-title';
    head.textContent = cmd.title;
    narration.appendChild(head);
  }
  wrapper.appendChild(narration);

  placeElement(wrapper, cmd.placement ?? 'below', cmd);

  const { createAnimation } = await import('../commands/animation');
  const savedScene = board.liveScene;
  board.liveScene = animSlot;
  try {
    await createAnimation({ ...cmd, id: `${cmd.id}-anim`, placement: 'below' });
  } finally {
    board.liveScene = savedScene;
  }
}

async function renderMermaid(cmd: BoardCommand): Promise<void> {
  const { renderMermaidCommand } = await import('../commands/mermaid');
  await renderMermaidCommand(cmd);
}

async function renderChart(cmd: BoardCommand): Promise<void> {
  const { renderChartCommand } = await import('../commands/chart');
  await renderChartCommand(cmd);
}

async function renderScene3d(cmd: BoardCommand): Promise<void> {
  const { renderScene3dCommand } = await import('../commands/scene3d');
  await renderScene3dCommand(cmd);
}

async function renderCode(cmd: BoardCommand): Promise<void> {
  const { renderCodeCommand } = await import('../commands/code');
  await renderCodeCommand(cmd);
}

async function renderDataStructure(cmd: BoardCommand): Promise<void> {
  const { renderDsCommand } = await import('../commands/ds');
  await renderDsCommand(cmd);
}

async function renderDiagram(cmd: BoardCommand): Promise<void> {
  const { renderDiagramCommand } = await import('../commands/diagram');
  await renderDiagramCommand(cmd);
}

async function renderAssessment(cmd: BoardCommand): Promise<void> {
  const { renderAssessmentCommand } = await import('../commands/assess');
  await renderAssessmentCommand(cmd);
}

function autoScroll(): void {
  const wrap = board.wrapEl;
  if (!wrap || !board.liveScene) return;
  const lastEl = board.liveScene.lastElementChild as HTMLElement | null;
  if (!lastEl || lastEl.classList.contains('bd-grid-bg')) return;
  const wrapRect = wrap.getBoundingClientRect();
  const elRect = lastEl.getBoundingClientRect();
  if (elRect.bottom > wrapRect.bottom - 20) {
    lastEl.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }
}
