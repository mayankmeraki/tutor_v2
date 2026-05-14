import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as Engine from './index';
import { board } from './state';

function setupBoardDom() {
  document.body.innerHTML = `
    <div id="bd-canvas-wrap" class="bd-canvas-wrap">
      <div id="bd-board-content" class="bd-board-content">
        <div id="bd-scenes-stack" class="bd-scenes-stack"></div>
      </div>
    </div>
  `;
  const wrap = document.getElementById('bd-canvas-wrap')!;
  const content = document.getElementById('bd-board-content')!;
  const stack = document.getElementById('bd-scenes-stack')!;
  Engine.init({
    rootEl: wrap,
    contentEl: content,
    scenesStackEl: stack,
    wrapEl: wrap,
  });
  return { wrap, content, stack };
}

beforeEach(() => {
  // Reset shared engine state between tests.
  board.commandQueue = [];
  board.cancelFlag = false;
  board.replayMode = false;
  board.zoom = 1;
  board.elements.clear();
  board.animations = [];
  board.scenes = [];
});

afterEach(() => {
  Engine.destroy();
  document.body.innerHTML = '';
});

describe('Board engine — initialization', () => {
  it('creates a #bd-live-scene with grid background', () => {
    setupBoardDom();
    const live = document.getElementById('bd-live-scene');
    expect(live).toBeTruthy();
    expect(live!.querySelector('.bd-grid-bg')).toBeTruthy();
  });
});

describe('Board engine — text command', () => {
  it('queues text and renders into the live scene', async () => {
    setupBoardDom();
    Engine.queueCommand({ cmd: 'text', text: 'hello world' });
    // Wait a few ticks for the async processor.
    await new Promise((r) => setTimeout(r, 100));
    const live = document.getElementById('bd-live-scene')!;
    expect(live.querySelector('.bd-text')).toBeTruthy();
  });

  it('honors replayMode by rendering text instantly (no .bd-char animation)', async () => {
    setupBoardDom();
    Engine.setReplayMode(true);
    Engine.queueCommand({ cmd: 'text', text: 'instant render' });
    await new Promise((r) => setTimeout(r, 60));
    const live = document.getElementById('bd-live-scene')!;
    const textEl = live.querySelector('.bd-text');
    expect(textEl).toBeTruthy();
    // In replay mode the engine sets textContent directly; no per-char spans.
    expect(textEl!.querySelector('.bd-char')).toBeNull();
    expect(textEl!.textContent).toBe('instant render');
  });
});

describe('Board engine — cancel', () => {
  it('cancel() drops pending commands from the queue', async () => {
    setupBoardDom();
    // Queue many slow commands (each text item runs animateText).
    for (let i = 0; i < 30; i++) {
      Engine.queueCommand({ cmd: 'text', text: `cmd ${i}`, charDelay: 5 });
    }
    Engine.cancel();
    expect(board.commandQueue.length).toBe(0);
    expect(board.cancelFlag).toBe(true);
  });
});

describe('Board engine — h1/h2/h3 commands', () => {
  it('h1 applies bd-size-h1 class', async () => {
    setupBoardDom();
    Engine.setReplayMode(true); // skip animation for fast assertion
    Engine.queueCommand({ cmd: 'h1', text: 'Title' });
    await new Promise((r) => setTimeout(r, 30));
    const live = document.getElementById('bd-live-scene')!;
    expect(live.querySelector('.bd-size-h1')).toBeTruthy();
  });
});

describe('Board engine — divider / gap', () => {
  it('divider renders an HR with bd-divider', async () => {
    setupBoardDom();
    Engine.queueCommand({ cmd: 'divider' });
    await new Promise((r) => setTimeout(r, 20));
    expect(document.querySelector('hr.bd-divider')).toBeTruthy();
  });

  it('gap renders a div with the requested height', async () => {
    setupBoardDom();
    Engine.queueCommand({ cmd: 'gap', height: 60 });
    await new Promise((r) => setTimeout(r, 20));
    const gap = document.querySelector('.bd-gap') as HTMLElement | null;
    expect(gap).toBeTruthy();
    expect(gap!.style.height).toBe('60px');
  });
});

describe('Board engine — clear / snapshotScene', () => {
  it('clearAll empties the live scene back to grid only', async () => {
    setupBoardDom();
    Engine.setReplayMode(true);
    Engine.queueCommand({ cmd: 'text', text: 'a' });
    Engine.queueCommand({ cmd: 'text', text: 'b' });
    Engine.queueCommand({ cmd: 'clear' });
    await new Promise((r) => setTimeout(r, 60));
    const live = document.getElementById('bd-live-scene')!;
    // Only the grid bg should remain.
    const otherChildren = Array.from(live.children).filter(
      (c) => !(c as HTMLElement).classList.contains('bd-grid-bg'),
    );
    expect(otherChildren).toHaveLength(0);
  });

  it('snapshotScene moves live scene into the stack', async () => {
    setupBoardDom();
    Engine.snapshotScene();
    const stack = document.getElementById('bd-scenes-stack')!;
    expect(stack.children.length).toBeGreaterThanOrEqual(1);
    expect(document.getElementById('bd-live-scene')).toBeTruthy();
  });
});

describe('Board engine — narrate without target', () => {
  it('silently skips narrate commands missing a target (legacy parity)', async () => {
    setupBoardDom();
    const before = document.querySelectorAll('.bd-text').length;
    Engine.queueCommand({ cmd: 'narrate', text: 'orphan' });
    await new Promise((r) => setTimeout(r, 30));
    const after = document.querySelectorAll('.bd-text').length;
    expect(after).toBe(before);
  });
});

describe('Board engine — zoom', () => {
  it('zoomIn applies a CSS scale transform on the content layer', () => {
    const { content } = setupBoardDom();
    Engine.zoomIn();
    expect(content.style.transform).toMatch(/scale\(/);
  });

  it('zoomReset restores zoom to 1', () => {
    setupBoardDom();
    Engine.zoomIn();
    Engine.zoomReset();
    expect(board.zoom).toBe(1);
  });
});

describe('Board engine — diagram (nodes/edges legacy shape)', () => {
  it('renders nodes + edges into an SVG element', async () => {
    setupBoardDom();
    Engine.queueCommand({
      cmd: 'diagram',
      style: 'crisp',
      width: 200,
      height: 100,
      nodes: [
        { id: 'a', x: 0, y: 0, label: 'API' },
        { id: 'b', x: 100, y: 0, label: 'DB' },
      ],
      edges: [{ from: 'a', to: 'b', label: 'reads' }],
    } as never);
    await new Promise((r) => setTimeout(r, 50));
    const svg = document.querySelector('.bd-diagram svg');
    expect(svg).toBeTruthy();
    // Two rectangles for nodes, at least one line for edges.
    expect(svg!.querySelectorAll('rect').length).toBeGreaterThanOrEqual(2);
  });
});

describe('Board engine — list', () => {
  it('renders one list-item per item', async () => {
    setupBoardDom();
    Engine.setReplayMode(true);
    Engine.queueCommand({
      cmd: 'list',
      style: 'bullet',
      items: ['one', 'two', 'three'],
    });
    await new Promise((r) => setTimeout(r, 80));
    expect(document.querySelectorAll('.bd-list .bd-list-item').length).toBe(3);
  });
});
