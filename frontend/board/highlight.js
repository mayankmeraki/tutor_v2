/**
 * Highlight — {ref:id} zoom-pulse via CSS class + scrollIntoView.
 * Replaces the coordinate-based overlay system with simple DOM operations.
 */

import { board } from './state.js';

/**
 * Highlight an element — scroll to it and add a glow animation.
 * @param {string} elementId - The element's DOM ID
 */
export function zoomPulse(elementId) {
  const entry = board.elements.get(elementId);
  if (!entry) {
    console.warn('[Ref] Element not found:', elementId,
      '— available:', [...board.elements.keys()].join(', '));
    return;
  }

  const el = entry.element;
  if (!el || !el.isConnected) return;

  // Add highlight glow
  el.classList.add('bd-highlight');

  // Scroll to element smoothly
  el.scrollIntoView({ behavior: 'smooth', block: 'center' });

  // Remove highlight after animation completes (4.3s)
  setTimeout(() => {
    el.classList.remove('bd-highlight');
  }, 4300);
}

/**
 * Scroll to an element by ID.
 * @param {string} elementId
 */
export function scrollToElement(elementId) {
  const entry = board.elements.get(elementId);
  if (!entry?.element?.isConnected) return;
  entry.element.scrollIntoView({ behavior: 'smooth', block: 'center' });
}
