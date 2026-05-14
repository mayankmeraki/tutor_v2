/**
 * Text Animator — character-by-character reveal.
 * Native TypeScript port of frontend-legacy/board/text-animator.js.
 */

import { board } from './state';

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export interface AnimateTextOptions {
  charDelay?: number;
  instant?: boolean;
}

export async function animateText(
  parentEl: HTMLElement,
  text: string | undefined,
  options: AnimateTextOptions = {},
): Promise<void> {
  if (!text) return;

  let str: string = text;
  if (typeof str === 'string' && str.indexOf('\\') !== -1) {
    str = str
      .replace(/\\n/g, '\n')
      .replace(/\\r/g, '\r')
      .replace(/\\t/g, '\t')
      .replace(/\\'/g, "'")
      .replace(/\\"/g, '"');
  }

  const queueLen = board.commandQueue.length;
  const animCount = board.animations.length;
  const instant =
    options.instant || board.replayMode || queueLen > 5 || animCount > 4;
  let delay = options.charDelay;
  if (delay === undefined) {
    delay = animCount > 2 ? 15 : animCount > 0 ? 25 : 35;
  }

  const hasNewlines = str.includes('\n');

  if (instant || delay === 0) {
    if (hasNewlines) {
      parentEl.innerHTML = str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\n/g, '<br>');
    } else {
      parentEl.textContent = str;
    }
    return;
  }

  const fragment = document.createDocumentFragment();
  const chars: HTMLElement[] = [];
  for (const ch of str) {
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

  for (const span of chars) {
    if (board.cancelFlag) {
      chars.forEach((s) => s.classList.add('bd-char-visible'));
      break;
    }
    span.classList.add('bd-char-visible');
    await sleep(delay);
  }

  if (hasNewlines) {
    parentEl.innerHTML = str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\n/g, '<br>');
  } else {
    parentEl.textContent = str;
  }
}
