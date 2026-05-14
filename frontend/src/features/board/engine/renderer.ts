/**
 * Renderer — creates styled DOM elements for board content.
 * Native TypeScript port of frontend-legacy/board/renderer.js.
 */

import type { BoardCommand } from './state';

const COLOR_MAP: Record<string, string> = {
  white: 'white',
  yellow: 'yellow',
  gold: 'gold',
  green: 'green',
  blue: 'cyan',
  red: 'red',
  cyan: 'cyan',
  dim: 'dim',
  '#e8e8e0': 'white',
  '#f5d97a': 'yellow',
  '#fbbf24': 'gold',
  '#34d399': 'green',
  '#7ed99a': 'green',
  '#53d8fb': 'cyan',
  '#ff6b6b': 'red',
  '#94a3b8': 'dim',
  '#e2e8f0': 'white',
  '#fb7185': 'red',
  '#a78bfa': 'cyan',
};

const SIZE_MAP: Record<string, string> = {
  h1: 'h1',
  h2: 'h2',
  h3: 'h3',
  text: 'text',
  body: 'text',
  small: 'small',
  label: 'label',
  caption: 'label',
};

export function colorClass(color?: string): string {
  if (!color) return 'bd-chalk-white';
  const key = typeof color === 'string' ? color.toLowerCase() : color;
  const mapped = COLOR_MAP[key] ?? COLOR_MAP[color];
  return `bd-chalk-${mapped ?? 'white'}`;
}

export function sizeClass(size?: string | number): string {
  if (size === undefined || size === null) return 'bd-size-text';
  if (typeof size === 'string') {
    const mapped = SIZE_MAP[size.toLowerCase()];
    return `bd-size-${mapped ?? 'text'}`;
  }
  if (size >= 24) return 'bd-size-h1';
  if (size >= 19) return 'bd-size-h2';
  if (size >= 16) return 'bd-size-text';
  if (size >= 12) return 'bd-size-small';
  return 'bd-size-label';
}

export function createElement(
  tag: keyof HTMLElementTagNameMap,
  cmd: BoardCommand,
  ...extraClasses: (string | undefined)[]
): HTMLElement {
  const el = document.createElement(tag);
  el.className = ['bd-el', ...extraClasses].filter(Boolean).join(' ');
  if (cmd.id) el.id = cmd.id;
  if (cmd.cmd) el.dataset.cmd = cmd.cmd;
  return el;
}

export function createStyledElement(
  tag: keyof HTMLElementTagNameMap,
  cmd: BoardCommand,
  ...extraClasses: (string | undefined)[]
): HTMLElement {
  return createElement(
    tag,
    cmd,
    colorClass(cmd.color),
    sizeClass(cmd.size),
    ...extraClasses,
  );
}
