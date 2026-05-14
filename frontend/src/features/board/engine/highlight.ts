/**
 * Highlight — zoom-pulse via CSS class + scrollIntoView.
 * Native TypeScript port of frontend-legacy/board/highlight.js.
 */

import { board } from './state';

export function zoomPulse(elementId: string): void {
  const entry = board.elements.get(elementId);
  if (!entry) return;
  const el = entry.element;
  if (!el || !el.isConnected) return;
  el.classList.add('bd-highlight');
  el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  setTimeout(() => el.classList.remove('bd-highlight'), 4300);
}

export function scrollToElement(elementId: string): void {
  const entry = board.elements.get(elementId);
  if (!entry?.element?.isConnected) return;
  entry.element.scrollIntoView({ behavior: 'smooth', block: 'center' });
}
