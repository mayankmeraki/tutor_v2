/**
 * Renderer — creates styled DOM elements for board content.
 * Pure functions that return DOM elements without side effects.
 */

/** Color name/hex → CSS class mapping */
const COLOR_MAP = {
  white: 'white', yellow: 'yellow', gold: 'gold', green: 'green',
  blue: 'cyan', red: 'red', cyan: 'cyan', dim: 'dim',
  '#e8e8e0': 'white', '#f5d97a': 'yellow', '#fbbf24': 'gold',
  '#34d399': 'green', '#7ed99a': 'green', '#53d8fb': 'cyan',
  '#ff6b6b': 'red', '#94a3b8': 'dim', '#e2e8f0': 'white',
  '#fb7185': 'red', '#a78bfa': 'cyan',
};

/** Size name → CSS class */
const SIZE_MAP = {
  h1: 'h1', h2: 'h2', h3: 'h3', text: 'text', body: 'text',
  small: 'small', label: 'label', caption: 'label',
};

/**
 * Resolve a color value to a CSS class name.
 * @param {string} color - 'cyan', '#53d8fb', etc.
 * @returns {string} CSS class like 'bd-chalk-cyan'
 */
export function colorClass(color) {
  if (!color) return 'bd-chalk-white';
  const mapped = COLOR_MAP[color.toLowerCase?.()] || COLOR_MAP[color];
  return `bd-chalk-${mapped || 'white'}`;
}

/**
 * Resolve a size value to a CSS class name.
 * @param {string|number} size - 'h1', 'text', 16, etc.
 * @returns {string} CSS class like 'bd-size-text'
 */
export function sizeClass(size) {
  if (!size) return 'bd-size-text';
  if (typeof size === 'string') {
    const mapped = SIZE_MAP[size.toLowerCase()];
    return `bd-size-${mapped || 'text'}`;
  }
  // Numeric → find closest semantic size
  if (size >= 24) return 'bd-size-h1';
  if (size >= 19) return 'bd-size-h2';
  if (size >= 16) return 'bd-size-text';
  if (size >= 12) return 'bd-size-small';
  return 'bd-size-label';
}

/**
 * Create a base board element.
 * @param {string} tag - HTML tag ('div', 'span', 'hr')
 * @param {Object} cmd - Command object with id, color, size
 * @param {string[]} extraClasses - Additional CSS classes
 * @returns {HTMLElement}
 */
export function createElement(tag, cmd, ...extraClasses) {
  const el = document.createElement(tag);
  el.className = ['bd-el', ...extraClasses].filter(Boolean).join(' ');
  if (cmd.id) el.id = cmd.id;
  if (cmd.cmd) el.dataset.cmd = cmd.cmd;
  return el;
}

/**
 * Create a text element with color and size classes.
 * @param {string} tag
 * @param {Object} cmd
 * @param {string[]} extraClasses
 * @returns {HTMLElement}
 */
export function createStyledElement(tag, cmd, ...extraClasses) {
  const el = createElement(tag, cmd, colorClass(cmd.color), sizeClass(cmd.size), ...extraClasses);
  return el;
}
