import { createElement } from '../engine/renderer';
import { placeElement } from '../engine/placement';
import type { BoardCommand } from '../engine/state';

let embedPromise: Promise<typeof import('vega-embed')['default']> | null = null;

async function getEmbed() {
  if (!embedPromise) {
    embedPromise = import('vega-embed').then((m) => m.default);
  }
  return embedPromise;
}

export async function renderChartCommand(cmd: BoardCommand): Promise<void> {
  const spec = (cmd as { spec?: object }).spec;
  if (!spec) return;
  const el = createElement('div', cmd, 'bd-chart');
  placeElement(el, cmd.placement ?? 'below', cmd);
  try {
    const embed = await getEmbed();
    await embed(el, spec as Record<string, unknown>, {
      actions: false,
      theme: 'dark',
      renderer: 'svg',
    });
  } catch (err) {
    el.innerHTML = `<pre class="text-bad text-xs">Chart error: ${(err as Error).message}</pre>`;
  }
}
