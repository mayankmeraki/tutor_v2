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

  // Normalize literal escape sequences from model JSON. The model
  // sometimes emits "\\n" inside `draw='{...}'` attribute strings, which
  // JSON.parse turns into the literal 2 chars `\n` (backslash + n) instead
  // of a real newline byte. Same for \r and \t. Convert them all here so
  // multi-line text always renders as line breaks regardless of how the
  // model escaped its output.
  if (typeof text === 'string' && text.indexOf('\\') !== -1) {
    text = text
      .replace(/\\n/g, '\n')
      .replace(/\\r/g, '\r')
      .replace(/\\t/g, '\t');
  }

  // Determine delay — faster when queue is backed up
  const queueLen = board.commandQueue.length;
  const animCount = board.animations.length;
  let instant = options.instant || board.replayMode || queueLen > 5 || animCount > 4;
  let delay = options.charDelay;
  if (delay === undefined) {
    delay = animCount > 2 ? 15 : animCount > 0 ? 25 : 35;
  }

  // Convert \n to line breaks for multi-line text (callouts, etc.)
  const hasNewlines = text.includes('\n');

  if (instant || delay === 0) {
    // Instant mode — handle newlines
    if (hasNewlines) {
      parentEl.innerHTML = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');
    } else {
      parentEl.textContent = text;
    }
    return;
  }

  // Create character spans (newlines → <br>)
  const fragment = document.createDocumentFragment();
  const chars = [];
  for (const ch of text) {
    if (ch === '\n') {
      const br = document.createElement('br');
      br.classList.add('bd-char-visible');
      fragment.appendChild(br);
      continue;
    }
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
  if (hasNewlines) {
    parentEl.innerHTML = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');
  } else {
    parentEl.textContent = text;
  }
}
