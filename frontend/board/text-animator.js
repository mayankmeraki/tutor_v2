/**
 * Text Animator — character-by-character reveal animation.
 * Creates spans for each character, reveals them progressively,
 * then collapses to plain text for DOM performance.
 */

import { board } from './state.js';

/**
 * Sleep for ms milliseconds (respects cancelFlag).
 * @param {number} ms
 * @returns {Promise<void>}
 */
export function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Animate text character-by-character into a parent element.
 * @param {HTMLElement} parentEl - Container to append text into
 * @param {string} text - Text to reveal
 * @param {Object} [options]
 * @param {number} [options.charDelay] - Ms between characters (0 = instant)
 * @param {boolean} [options.instant] - Skip animation entirely
 * @returns {Promise<void>}
 */
export async function animateText(parentEl, text, options = {}) {
  if (!text) return;

  // Determine delay — faster when queue is backed up
  const queueLen = board.commandQueue.length;
  const animCount = board.animations.length;
  let instant = options.instant || queueLen > 5 || animCount > 4;
  let delay = options.charDelay;
  if (delay === undefined) {
    delay = animCount > 2 ? 15 : animCount > 0 ? 25 : 35;
  }

  if (instant || delay === 0) {
    // Instant mode — just set textContent
    parentEl.textContent = text;
    return;
  }

  // Create character spans
  const fragment = document.createDocumentFragment();
  const chars = [];
  for (const ch of text) {
    const span = document.createElement('span');
    span.className = 'bd-char';
    span.textContent = ch;
    chars.push(span);
    fragment.appendChild(span);
  }
  parentEl.appendChild(fragment);

  // Reveal characters progressively
  for (const span of chars) {
    if (board.cancelFlag) {
      // Cancel — reveal remaining instantly
      chars.forEach(s => s.classList.add('bd-char-visible'));
      break;
    }
    span.classList.add('bd-char-visible');
    await sleep(delay);
  }

  // Collapse spans to plain text for DOM performance
  parentEl.textContent = text;
}
