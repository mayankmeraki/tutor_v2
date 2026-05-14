/**
 * Board State — single source of truth for the DOM board engine.
 * Replaces the scattered bdLayout, bdElementRegistry, bdActiveAnimations, etc.
 */

export const board = {
  /** @type {HTMLElement|null} Current live scene element */
  liveScene: null,

  /** @type {HTMLElement|null} Current flex row (for row-start/row-next) */
  currentRow: null,

  /** @type {HTMLElement|null} Current columns grid (for columns/columns-end) */
  currentColumns: null,

  /** @type {boolean} Cancel flag — stops animations and text reveal */
  cancelFlag: false,

  /** @type {Array<Object>} Command queue — processed sequentially */
  commandQueue: [],

  /** @type {boolean} Whether the queue processor is running */
  isProcessing: false,

  /** @type {Map<string, {element: HTMLElement, scene: number}>} Element registry for refs */
  elements: new Map(),

  /** @type {Array<{element: HTMLElement}>} Past scene snapshots */
  scenes: [],

  /** @type {Array<{container: HTMLElement, instance: Object}>} Active p5 animations */
  animations: [],

  /** @type {number} Current zoom level */
  zoom: 1,

  /** @type {Map<string, number>} Animation retry counts per ID */
  animRetries: new Map(),

  /** @type {string} API base URL */
  apiUrl: '',
};

/**
 * Reset board state for a new session.
 */
export function resetState() {
  board.liveScene = null;
  board.currentRow = null;
  board.currentColumns = null;
  board.cancelFlag = false;
  board.commandQueue = [];
  board.isProcessing = false;
  board.elements.clear();
  board.scenes = [];
  board.animations.forEach(a => { try { a.instance.remove(); } catch(e) {} });
  board.animations = [];
  board.zoom = 1;
  board.animRetries.clear();
}

/**
 * Register an element in the registry for {ref:id} and beside:/below: lookups.
 * @param {string} id - Element ID
 * @param {HTMLElement} element - DOM element
 */
export function registerElement(id, element) {
  if (!id) return;
  board.elements.set(id, {
    element,
    scene: board.scenes.length,
  });
}

/**
 * Look up an element, only returning it if it's in the current scene.
 * @param {string} id
 * @returns {HTMLElement|null}
 */
export function getElement(id) {
  const entry = board.elements.get(id);
  if (!entry) return null;
  if (entry.scene !== board.scenes.length) return null; // wrong scene
  return entry.element;
}

/**
 * Look up any element regardless of scene (for highlighting).
 * @param {string} id
 * @returns {{element: HTMLElement, scene: number}|null}
 */
export function getElementAny(id) {
  return board.elements.get(id) || null;
}

/**
 * Clear element registry (between scenes).
 */
export function clearElements() {
  // Don't clear — old scene elements stay for cross-scene {ref:}
  // Just note: getElement() filters by current scene
}

/**
 * End the current row if one is active.
 */
export function endRow() {
  board.currentRow = null;
}
