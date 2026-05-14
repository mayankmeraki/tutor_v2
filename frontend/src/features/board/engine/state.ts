/**
 * Board State — single source of truth for the DOM board engine.
 * Native TypeScript port of frontend-legacy/board/state.js.
 */

export interface ElementEntry {
  element: HTMLElement;
  scene: number;
}

export interface AnimationEntry {
  container: HTMLElement;
  instance: { remove: () => void; loop?: () => void; noLoop?: () => void; redraw?: () => void };
  _running?: boolean;
}

export interface BoardState {
  liveScene: HTMLElement | null;
  currentRow: HTMLElement | null;
  currentColumns: HTMLElement | null;
  cancelFlag: boolean;
  commandQueue: BoardCommand[];
  isProcessing: boolean;
  elements: Map<string, ElementEntry>;
  scenes: { element: HTMLElement }[];
  animations: AnimationEntry[];
  zoom: number;
  animRetries: Map<string, number>;
  apiUrl: string;
  replayMode: boolean;
  rootEl: HTMLElement | null;
  contentEl: HTMLElement | null;
  scenesStackEl: HTMLElement | null;
  wrapEl: HTMLElement | null;
}

export interface BoardCommand {
  cmd: string;
  id?: string;
  target?: string;
  source?: string;
  text?: string;
  placement?: string;
  color?: string;
  size?: string | number;
  charDelay?: number;
  height?: number;
  cols?: number;
  items?: string[];
  style?: string;
  pos?: string;
  n?: number;
  note?: string;
  type?: string;
  [key: string]: unknown;
}

export const board: BoardState = {
  liveScene: null,
  currentRow: null,
  currentColumns: null,
  cancelFlag: false,
  commandQueue: [],
  isProcessing: false,
  elements: new Map(),
  scenes: [],
  animations: [],
  zoom: 1,
  animRetries: new Map(),
  apiUrl: '',
  replayMode: false,
  rootEl: null,
  contentEl: null,
  scenesStackEl: null,
  wrapEl: null,
};

export function resetState(): void {
  board.liveScene = null;
  board.currentRow = null;
  board.currentColumns = null;
  board.cancelFlag = false;
  board.commandQueue = [];
  board.isProcessing = false;
  board.elements.clear();
  board.scenes = [];
  for (const a of board.animations) {
    try {
      a.instance.remove();
    } catch {
      /* ignore */
    }
  }
  board.animations = [];
  board.zoom = 1;
  board.animRetries.clear();
}

export function registerElement(id: string | undefined, element: HTMLElement): void {
  if (!id) return;
  board.elements.set(id, { element, scene: board.scenes.length });
}

export function getElement(id: string): HTMLElement | null {
  const entry = board.elements.get(id);
  if (!entry) return null;
  if (entry.scene !== board.scenes.length) return null;
  return entry.element;
}

export function getElementAny(id: string): ElementEntry | null {
  return board.elements.get(id) ?? null;
}

export function endRow(): void {
  board.currentRow = null;
}
