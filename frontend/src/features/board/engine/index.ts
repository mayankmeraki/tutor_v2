/**
 * Board Engine — public TypeScript API.
 * Native port of frontend-legacy/board/index.js.
 */

import { board, resetState, type BoardCommand } from './state';
import { runCommand } from './commands';
import { snapshotScene, clearAll, updateAnimationVisibility } from './scene';
import { zoomPulse, scrollToElement } from './highlight';

export interface InitOptions {
  apiUrl?: string;
  rootEl: HTMLElement;
  contentEl: HTMLElement;
  scenesStackEl: HTMLElement;
  wrapEl: HTMLElement;
}

export function init(options: InitOptions): void {
  const { rootEl, contentEl, scenesStackEl, wrapEl, apiUrl } = options;
  board.apiUrl = apiUrl ?? '';
  board.cancelFlag = false;
  board.rootEl = rootEl;
  board.contentEl = contentEl;
  board.scenesStackEl = scenesStackEl;
  board.wrapEl = wrapEl;

  let liveScene = contentEl.querySelector<HTMLElement>('#bd-live-scene');
  if (!liveScene) {
    liveScene = document.createElement('div');
    liveScene.id = 'bd-live-scene';
    liveScene.className = 'bd-scene';
    liveScene.innerHTML = '<div class="bd-grid-bg"></div>';
    contentEl.appendChild(liveScene);
  }
  board.liveScene = liveScene;
  board.currentRow = null;

  initZoom(wrapEl);
  initScrollVisibility(wrapEl);

  if (board.commandQueue.length > 0 && !board.isProcessing) {
    void processQueue();
  }
}

export function destroy(): void {
  resetState();
  board.rootEl = null;
  board.contentEl = null;
  board.scenesStackEl = null;
  board.wrapEl = null;
}

export function queueCommand(cmd: BoardCommand): void {
  board.commandQueue.push(cmd);
  if (!board.isProcessing) void processQueue();
}

export function cancel(): void {
  // Drop pending commands AND signal any in-flight processor to bail out
  // (legacy parity: `Board.cancel` clears the queue immediately).
  board.cancelFlag = true;
  board.commandQueue = [];
}

export function setReplayMode(on: boolean): void {
  board.replayMode = on;
}

export function resume(): void {
  board.cancelFlag = false;
  if (board.commandQueue.length > 0 && !board.isProcessing) void processQueue();
}

async function processQueue(): Promise<void> {
  if (board.isProcessing) return;
  board.isProcessing = true;

  if (!board.liveScene) {
    let waited = 0;
    while (!board.liveScene && waited < 2000) {
      await new Promise((r) => setTimeout(r, 16));
      waited += 16;
    }
    if (!board.liveScene) {
      board.commandQueue = [];
      board.isProcessing = false;
      return;
    }
  }

  while (board.commandQueue.length > 0) {
    if (board.cancelFlag) {
      board.commandQueue = [];
      break;
    }
    const cmd = board.commandQueue.shift();
    if (!cmd) continue;
    try {
      await runCommand(cmd);
    } catch (e) {
      // eslint-disable-next-line no-console
      console.warn('[Board] Command failed:', cmd.cmd, e);
    }
  }

  board.isProcessing = false;
}

function initZoom(wrap: HTMLElement): void {
  let lastTouchDist = 0;

  wrap.addEventListener(
    'wheel',
    (e: WheelEvent) => {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        applyZoom(board.zoom + (e.deltaY > 0 ? -0.05 : 0.05));
      }
    },
    { passive: false },
  );

  wrap.addEventListener('touchstart', (e: TouchEvent) => {
    if (e.touches.length === 2) {
      const a = e.touches[0];
      const b = e.touches[1];
      lastTouchDist = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
    }
  });
  wrap.addEventListener('touchmove', (e: TouchEvent) => {
    if (e.touches.length === 2) {
      const a = e.touches[0];
      const b = e.touches[1];
      const dist = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
      if (lastTouchDist > 0) {
        const ratio = dist / lastTouchDist;
        applyZoom(board.zoom * ratio);
      }
      lastTouchDist = dist;
    }
  });

  document.addEventListener('keydown', (e) => {
    if (!(e.ctrlKey || e.metaKey)) return;
    if (e.key === '+' || e.key === '=') {
      e.preventDefault();
      applyZoom(board.zoom + 0.1);
    } else if (e.key === '-' || e.key === '_') {
      e.preventDefault();
      applyZoom(board.zoom - 0.1);
    } else if (e.key === '0') {
      e.preventDefault();
      applyZoom(1);
    }
  });
}

function applyZoom(z: number): void {
  board.zoom = Math.max(0.4, Math.min(3, z));
  if (board.contentEl) {
    board.contentEl.style.transformOrigin = 'top left';
    board.contentEl.style.transform = `scale(${board.zoom})`;
  }
}

export function zoomIn(): void {
  applyZoom(board.zoom + 0.1);
}
export function zoomOut(): void {
  applyZoom(board.zoom - 0.1);
}
export function zoomReset(): void {
  applyZoom(1);
}

function initScrollVisibility(wrap: HTMLElement): void {
  let timer: ReturnType<typeof setTimeout> | null = null;
  wrap.addEventListener(
    'scroll',
    () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => updateAnimationVisibility(), 200);
    },
    { passive: true },
  );
}

export {
  snapshotScene,
  clearAll,
  updateAnimationVisibility,
  zoomPulse,
  scrollToElement,
};

export const Board = {
  init,
  destroy,
  queueCommand,
  cancel,
  resume,
  setReplayMode,
  snapshotScene,
  clearAll,
  zoomIn,
  zoomOut,
  zoomReset,
  zoomPulse,
  scrollToElement,
  updateAnimationVisibility,
  state: board,
};

export type { BoardCommand };
