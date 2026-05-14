/**
 * Scene Management — snapshot, clear, freeze, animation visibility.
 * Native TypeScript port of frontend-legacy/board/scene.js.
 */

import { board, endRow } from './state';

export function snapshotScene(): void {
  if (!board.liveScene) return;
  const stack = board.scenesStackEl;
  if (!stack) return;

  const frozen = board.liveScene;
  frozen.removeAttribute('id');
  frozen.classList.add('bd-scene-frozen');
  frozen.dataset.sceneIndex = String(board.scenes.length);
  stack.appendChild(frozen);
  board.scenes.push({ element: frozen });

  for (const entry of board.animations) {
    try {
      entry.instance.noLoop?.();
    } catch {
      /* ignore */
    }
  }
  board.animations = [];

  const next = document.createElement('div');
  next.id = 'bd-live-scene';
  next.className = 'bd-scene';
  next.innerHTML = '<div class="bd-grid-bg"></div>';
  board.contentEl?.appendChild(next);

  board.liveScene = next;
  board.currentRow = null;
  board.animRetries.clear();
}

export function clearAll(): void {
  if (board.scenesStackEl) board.scenesStackEl.innerHTML = '';
  board.scenes = [];
  board.elements.clear();
  for (const a of board.animations) {
    try {
      a.instance.remove();
    } catch {
      /* ignore */
    }
  }
  board.animations = [];
  board.animRetries.clear();
  endRow();

  if (board.liveScene) {
    board.liveScene.innerHTML = '<div class="bd-grid-bg"></div>';
  }
}

export function updateAnimationVisibility(): void {
  const wrap = board.wrapEl;
  if (!wrap) return;
  const wrapRect = wrap.getBoundingClientRect();
  const margin = 200;

  for (const entry of board.animations) {
    if (!entry.container || !entry.instance) continue;
    const rect = entry.container.getBoundingClientRect();
    const visible =
      rect.bottom > wrapRect.top - margin && rect.top < wrapRect.bottom + margin;
    try {
      if (visible && !entry._running) {
        entry.instance.loop?.();
        try {
          entry.instance.redraw?.();
        } catch {
          /* ignore */
        }
        entry._running = true;
      } else if (!visible && entry._running !== false) {
        entry.instance.noLoop?.();
        entry._running = false;
      }
    } catch {
      /* ignore */
    }
  }
}
