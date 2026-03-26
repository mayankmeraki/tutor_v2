/**
 * Board Engine — public API.
 * Entry point for the DOM-based board rendering system.
 *
 * Usage:
 *   import { Board } from './board/index.js';
 *   Board.init(apiUrl);
 *   Board.processCommand(cmd);
 *   Board.snapshotScene();
 *   Board.zoomPulse('eq1');
 */

import { board, resetState, endRow } from './state.js';
import { runCommand } from './commands.js';
import { snapshotScene, clearAll, updateAnimationVisibility } from './scene.js';
import { zoomPulse, scrollToElement } from './highlight.js';

/**
 * Initialize the board DOM structure.
 * @param {string} apiUrl - Backend API URL for Haiku fix endpoint
 */
function init(apiUrl) {
  board.apiUrl = apiUrl || '';
  board.cancelFlag = false;

  // Find or create the live scene
  let liveScene = document.getElementById('bd-live-scene');
  if (!liveScene) {
    const boardContent = document.getElementById('bd-board-content');
    if (boardContent) {
      liveScene = document.createElement('div');
      liveScene.id = 'bd-live-scene';
      liveScene.className = 'bd-scene';
      liveScene.innerHTML = '<div class="bd-grid-bg"></div>';
      boardContent.appendChild(liveScene);
    }
  }
  board.liveScene = liveScene;
  board.currentRow = null;

  // Init zoom
  initZoom();

  // Init scroll-based animation visibility
  const wrap = document.getElementById('bd-canvas-wrap');
  if (wrap && !wrap._bdScrollInit) {
    wrap._bdScrollInit = true;
    let scrollTimer;
    wrap.addEventListener('scroll', () => {
      if (scrollTimer) clearTimeout(scrollTimer);
      scrollTimer = setTimeout(() => updateAnimationVisibility(), 200);
    }, { passive: true });
  }

  // Start processing queue if commands are waiting
  if (board.commandQueue.length > 0 && !board.isProcessing) {
    processQueue();
  }
}

/**
 * Add a command to the queue and start processing.
 * @param {Object} cmd - Draw command JSON
 */
function queueCommand(cmd) {
  board.commandQueue.push(cmd);
  if (!board.isProcessing) processQueue();
}

/**
 * Process commands from the queue sequentially.
 */
async function processQueue() {
  if (board.isProcessing) return;
  board.isProcessing = true;

  while (board.commandQueue.length > 0) {
    if (board.cancelFlag) {
      board.commandQueue = [];
      break;
    }
    const cmd = board.commandQueue.shift();
    try {
      await runCommand(cmd);
    } catch (e) {
      console.error('[Board] Command error:', e.message, cmd);
    }
  }

  board.isProcessing = false;
}

/**
 * Cancel all pending operations.
 */
function cancel() {
  board.cancelFlag = true;
  board.commandQueue = [];
  board.isProcessing = false;
}

/**
 * Full board cleanup for session end / navigation.
 */
function cleanup() {
  cancel();
  resetState();
}

/**
 * Initialize zoom controls.
 */
function initZoom() {
  const wrap = document.getElementById('bd-canvas-wrap');
  if (!wrap || wrap._bdZoomInit) return;
  wrap._bdZoomInit = true;

  function applyZoom() {
    const z = board.zoom;
    const content = document.getElementById('bd-board-content');
    if (content) {
      content.style.transformOrigin = 'top left';
      content.style.transform = z === 1 ? '' : `scale(${z})`;
    }
    const label = document.getElementById('bd-zoom-level');
    if (label) label.textContent = Math.round(z * 100) + '%';
  }

  // Ctrl+scroll zoom
  wrap.addEventListener('wheel', e => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const oldZ = board.zoom;
      board.zoom = Math.max(0.4, Math.min(4, oldZ * (1 - e.deltaY * 0.003)));
      applyZoom();
    }
  }, { passive: false });

  // Pinch zoom
  let lastPinchDist = 0;
  wrap.addEventListener('touchstart', e => {
    if (e.touches.length === 2) {
      lastPinchDist = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
    }
  }, { passive: true });
  wrap.addEventListener('touchmove', e => {
    if (e.touches.length === 2 && lastPinchDist > 0) {
      const dist = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
      board.zoom = Math.max(0.4, Math.min(4, board.zoom * dist / lastPinchDist));
      lastPinchDist = dist;
      applyZoom();
    }
  }, { passive: true });
  wrap.addEventListener('touchend', () => { lastPinchDist = 0; }, { passive: true });

  // Toolbar buttons
  window.bdZoomIn = () => { board.zoom = Math.min(4, board.zoom * 1.25); applyZoom(); };
  window.bdZoomOut = () => { board.zoom = Math.max(0.4, board.zoom / 1.25); applyZoom(); };
  window.bdZoomReset = () => { board.zoom = 1; applyZoom(); };

  // Keyboard shortcuts
  document.addEventListener('keydown', e => {
    if (!board.liveScene) return;
    if ((e.ctrlKey || e.metaKey) && (e.key === '=' || e.key === '+')) { e.preventDefault(); window.bdZoomIn(); }
    else if ((e.ctrlKey || e.metaKey) && e.key === '-') { e.preventDefault(); window.bdZoomOut(); }
    else if ((e.ctrlKey || e.metaKey) && e.key === '0') { e.preventDefault(); window.bdZoomReset(); }
  });
}

// ── Public API ──

export const Board = {
  init,
  queueCommand,
  processQueue,
  cancel,
  cleanup,
  snapshotScene,
  clearAll,
  zoomPulse,
  scrollToElement,

  /** Direct access to state (for integration with existing code) */
  get state() { return board; },
};

// Also expose on window for non-module contexts
if (typeof window !== 'undefined') {
  window.BoardEngine = Board;
}
