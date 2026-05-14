import { createElement } from '../engine/renderer';
import { placeElement } from '../engine/placement';
import type { BoardCommand } from '../engine/state';

interface AssessCommand extends BoardCommand {
  question?: string;
  prompt?: string;
  options?: { id: string; label: string; correct?: boolean }[];
  correct?: string | number | boolean;
  answer?: string;
  errors?: { id: string; line?: number; description?: string }[];
}

export async function renderAssessmentCommand(cmd: BoardCommand): Promise<void> {
  const c = cmd as AssessCommand;
  const el = createElement('div', cmd, 'bd-assess', `bd-assess-${cmd.cmd}`);
  placeElement(el, cmd.placement ?? 'below', cmd);

  const prompt = c.prompt ?? c.question ?? c.text;
  if (prompt) {
    const q = document.createElement('div');
    q.className = 'bd-assess-prompt';
    q.textContent = prompt;
    el.appendChild(q);
  }

  switch (cmd.cmd) {
    case 'assess-mcq':
      renderMcq(el, c);
      break;
    case 'assess-freetext':
    case 'assess-teachback':
      renderFreeText(el, c);
      break;
    case 'assess-spot-error':
      renderSpotError(el, c);
      break;
    case 'assess-confidence':
      renderConfidence(el, c);
      break;
  }
}

function renderMcq(el: HTMLElement, cmd: AssessCommand) {
  const wrap = document.createElement('div');
  wrap.className = 'bd-assess-options';
  for (const opt of cmd.options ?? []) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'bd-assess-option';
    btn.dataset.id = opt.id;
    btn.textContent = opt.label;
    btn.addEventListener('click', () => {
      btn.classList.add(opt.correct ? 'bd-assess-correct' : 'bd-assess-wrong');
    });
    wrap.appendChild(btn);
  }
  el.appendChild(wrap);
}

function renderFreeText(el: HTMLElement, _cmd: AssessCommand) {
  const ta = document.createElement('textarea');
  ta.className = 'bd-assess-textarea';
  ta.rows = 3;
  ta.placeholder = 'Type your answer...';
  el.appendChild(ta);
  const submit = document.createElement('button');
  submit.type = 'button';
  submit.className = 'bd-assess-submit';
  submit.textContent = 'Submit';
  el.appendChild(submit);
}

function renderSpotError(el: HTMLElement, cmd: AssessCommand) {
  const list = document.createElement('div');
  list.className = 'bd-assess-errors';
  for (const err of cmd.errors ?? []) {
    const item = document.createElement('div');
    item.className = 'bd-assess-error-item';
    item.textContent =
      (err.line !== undefined ? `Line ${err.line}: ` : '') +
      (err.description ?? err.id);
    list.appendChild(item);
  }
  el.appendChild(list);
}

function renderConfidence(el: HTMLElement, _cmd: AssessCommand) {
  const wrap = document.createElement('div');
  wrap.className = 'bd-assess-confidence';
  for (let i = 1; i <= 5; i++) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'bd-assess-conf-btn';
    btn.textContent = String(i);
    btn.dataset.value = String(i);
    wrap.appendChild(btn);
  }
  el.appendChild(wrap);
}
