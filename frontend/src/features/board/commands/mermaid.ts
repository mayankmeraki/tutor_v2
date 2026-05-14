import { createElement } from '../engine/renderer';
import { placeElement } from '../engine/placement';
import type { BoardCommand } from '../engine/state';

let mermaidPromise: Promise<typeof import('mermaid').default> | null = null;
let mermaidId = 0;

async function getMermaid() {
  if (!mermaidPromise) {
    mermaidPromise = import('mermaid').then((m) => {
      m.default.initialize({
        startOnLoad: false,
        theme: 'dark',
        themeVariables: {
          background: '#0a0d0b',
          primaryColor: '#191c1a',
          primaryTextColor: '#ececec',
          lineColor: '#5eead4',
        },
      });
      return m.default;
    });
  }
  return mermaidPromise;
}

export async function renderMermaidCommand(cmd: BoardCommand): Promise<void> {
  const source = (cmd as { source?: string; text?: string }).source ?? cmd.text;
  if (!source) return;
  const el = createElement('div', cmd, 'bd-mermaid');
  placeElement(el, cmd.placement ?? 'below', cmd);
  try {
    const mermaid = await getMermaid();
    const id = `bd-mermaid-${++mermaidId}`;
    const { svg } = await mermaid.render(id, source);
    el.innerHTML = svg;
  } catch (err) {
    el.innerHTML = `<pre class="text-bad text-xs">Mermaid error: ${(err as Error).message}</pre>`;
  }
}
