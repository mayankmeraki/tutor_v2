/**
 * Scene Management — snapshot, clear, freeze.
 * Dramatically simpler than canvas snapshots — just moves DOM elements.
 * No JPEG conversion. No rasterization. No DPR math.
 */

import { board, endRow } from './state.js';

/**
 * Snapshot the current scene — freeze it and start a new one.
 * The live scene's DOM elements simply move to the scenes stack.
 */
export function snapshotScene() {
  if (!board.liveScene) return;

  const scenesStack = document.getElementById('bd-scenes-stack');
  if (!scenesStack) return;

  // Freeze the live scene — move it to the stack
  const frozenScene = board.liveScene;
  frozenScene.removeAttribute('id');
  frozenScene.classList.add('bd-scene-frozen');
  frozenScene.dataset.sceneIndex = board.scenes.length;

  scenesStack.appendChild(frozenScene);
  board.scenes.push({ element: frozenScene });

  // Pause animations in the frozen scene
  board.animations.forEach(entry => {
    try { entry.instance.noLoop(); } catch (e) {}
  });
  board.animations = [];

  // Create a fresh live scene
  const newScene = document.createElement('div');
  newScene.id = 'bd-live-scene';
  newScene.className = 'bd-scene';
  newScene.innerHTML = '<div class="bd-grid-bg"></div>';

  const boardContent = document.getElementById('bd-board-content');
  if (boardContent) {
    boardContent.appendChild(newScene);
  }

  board.liveScene = newScene;
  board.currentRow = null;
  board.animRetries.clear();

  console.log(`[Scene] Snapshot ${board.scenes.length - 1} — DOM preserved (no JPEG)`);
}

/**
 * Clear all board content — reset everything.
 */
export function clearAll() {
  const scenesStack = document.getElementById('bd-scenes-stack');
  if (scenesStack) scenesStack.innerHTML = '';

  board.scenes = [];
  board.elements.clear();
  board.animations.forEach(a => { try { a.instance.remove(); } catch (e) {} });
  board.animations = [];
  board.animRetries.clear();
  endRow();

  // Reset live scene
  if (board.liveScene) {
    board.liveScene.innerHTML = '<div class="bd-grid-bg"></div>';
  }
}

/**
 * Update animation visibility — pause off-screen, resume on-screen.
 * Called on scroll to save CPU.
 */
export function updateAnimationVisibility() {
  const wrap = document.getElementById('bd-canvas-wrap');
  if (!wrap) return;

  const wrapRect = wrap.getBoundingClientRect();
  const margin = 200; // keep running slightly outside viewport

  board.animations.forEach(entry => {
    if (!entry.container || !entry.instance) return;
    const rect = entry.container.getBoundingClientRect();
    const visible = rect.bottom > wrapRect.top - margin &&
                    rect.top < wrapRect.bottom + margin;

    try {
      if (visible && !entry._running) {
        entry.instance.loop();
        // Force a redraw to avoid blank canvas on resume
        try { entry.instance.redraw(); } catch (_) {}
        entry._running = true;
      } else if (!visible && entry._running !== false) {
        entry.instance.noLoop();
        entry._running = false;
      }
    } catch (e) {}
  });
}
