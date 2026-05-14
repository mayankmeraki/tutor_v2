import { createElement } from '../engine/renderer';
import { placeElement } from '../engine/placement';
import type { BoardCommand } from '../engine/state';

interface DsCommand extends BoardCommand {
  type?: string;
  data?: unknown;
  pointers?: Record<string, number | string>;
  highlight?: (number | string)[];
}

export async function renderDsCommand(cmd: BoardCommand): Promise<void> {
  const c = cmd as DsCommand;
  const el = createElement('div', cmd, 'bd-ds', `bd-ds-${c.type ?? 'array'}`);
  placeElement(el, cmd.placement ?? 'below', cmd);

  const type = c.type ?? 'array';
  if (type === 'array' || type === 'stack' || type === 'queue') {
    renderArray(el, c);
  } else if (type === 'tree' || type === 'graph') {
    renderTree(el, c);
  } else if (type === 'linked-list') {
    renderLinkedList(el, c);
  } else if (type === 'matrix' || type === 'grid') {
    renderMatrix(el, c);
  } else if (type === 'hash-map') {
    renderHashMap(el, c);
  } else {
    renderArray(el, c);
  }
}

function renderArray(el: HTMLElement, cmd: DsCommand) {
  const data = (cmd.data ?? []) as (string | number)[];
  const highlight = new Set((cmd.highlight ?? []).map(String));
  const wrap = document.createElement('div');
  wrap.className = 'bd-ds-array';
  data.forEach((v, i) => {
    const cell = document.createElement('div');
    cell.className = 'bd-ds-cell';
    cell.dataset.index = String(i);
    cell.textContent = String(v);
    if (highlight.has(String(i))) cell.classList.add('bd-ds-highlight');
    wrap.appendChild(cell);
  });
  el.appendChild(wrap);
  if (cmd.pointers) {
    const ptrs = document.createElement('div');
    ptrs.className = 'bd-ds-pointers';
    for (const [name, idx] of Object.entries(cmd.pointers)) {
      const p = document.createElement('span');
      p.className = 'bd-ds-pointer';
      p.dataset.index = String(idx);
      p.textContent = `↑ ${name}`;
      ptrs.appendChild(p);
    }
    el.appendChild(ptrs);
  }
}

function renderTree(el: HTMLElement, cmd: DsCommand) {
  const tree = document.createElement('pre');
  tree.className = 'bd-ds-tree font-mono text-sm';
  tree.textContent = JSON.stringify(cmd.data, null, 2);
  el.appendChild(tree);
}

function renderLinkedList(el: HTMLElement, cmd: DsCommand) {
  const data = (cmd.data ?? []) as (string | number)[];
  const wrap = document.createElement('div');
  wrap.className = 'bd-ds-linked';
  data.forEach((v, i) => {
    const node = document.createElement('div');
    node.className = 'bd-ds-node';
    node.textContent = String(v);
    wrap.appendChild(node);
    if (i < data.length - 1) {
      const arr = document.createElement('span');
      arr.className = 'bd-ds-arrow';
      arr.textContent = '→';
      wrap.appendChild(arr);
    }
  });
  el.appendChild(wrap);
}

function renderMatrix(el: HTMLElement, cmd: DsCommand) {
  const data = (cmd.data ?? []) as (string | number)[][];
  const tbl = document.createElement('table');
  tbl.className = 'bd-ds-matrix';
  for (const row of data) {
    const tr = document.createElement('tr');
    for (const v of row) {
      const td = document.createElement('td');
      td.textContent = String(v);
      tr.appendChild(td);
    }
    tbl.appendChild(tr);
  }
  el.appendChild(tbl);
}

function renderHashMap(el: HTMLElement, cmd: DsCommand) {
  const data = (cmd.data ?? {}) as Record<string, unknown>;
  const wrap = document.createElement('div');
  wrap.className = 'bd-ds-hashmap';
  for (const [k, v] of Object.entries(data)) {
    const row = document.createElement('div');
    row.className = 'bd-ds-hash-row';
    row.innerHTML = `<span class="bd-ds-key">${k}</span> → <span class="bd-ds-val">${String(v)}</span>`;
    wrap.appendChild(row);
  }
  el.appendChild(wrap);
}

/**
 * Re-render a data-structure container in place (used by the `update` command).
 * Carries over the original dataset.type when the update command omits it so
 * the existing layout is preserved.
 */
export async function updateDsCommand(
  container: HTMLElement,
  cmd: BoardCommand,
): Promise<void> {
  const c = cmd as DsCommand;
  const type =
    c.type ??
    (Array.from(container.classList)
      .find((cls) => cls.startsWith('bd-ds-'))
      ?.replace(/^bd-ds-/, '') ??
      'array');
  container.innerHTML = '';
  const proxy = { ...c, type } as DsCommand;
  if (type === 'array' || type === 'stack' || type === 'queue') renderArray(container, proxy);
  else if (type === 'tree' || type === 'graph') renderTree(container, proxy);
  else if (type === 'linked-list') renderLinkedList(container, proxy);
  else if (type === 'matrix' || type === 'grid') renderMatrix(container, proxy);
  else if (type === 'hash-map') renderHashMap(container, proxy);
  else renderArray(container, proxy);
}
