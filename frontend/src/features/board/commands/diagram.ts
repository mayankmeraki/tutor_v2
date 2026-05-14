import { createElement } from '../engine/renderer';
import { placeElement } from '../engine/placement';
import type { BoardCommand } from '../engine/state';

/**
 * Diagram command — supports two shapes for legacy parity:
 *   1. New: `{ primitives: [{ type, props }] }` (rough/crisp SVG primitives)
 *   2. Legacy bundle.js: `{ nodes: [{id, x, y, label, shape}], edges: [{from,to,label}] }`
 */

interface PrimitivesDiagram extends BoardCommand {
  style?: 'sketch' | 'crisp';
  width?: number;
  height?: number;
  primitives?: { type: string; props: Record<string, unknown> }[];
}

interface NodeEdgeDiagram extends BoardCommand {
  style?: 'sketch' | 'crisp';
  width?: number;
  height?: number;
  nodes?: {
    id: string;
    x: number;
    y: number;
    label?: string;
    shape?: 'rect' | 'ellipse' | 'circle' | 'diamond';
    color?: string;
  }[];
  edges?: {
    from: string;
    to: string;
    label?: string;
    arrow?: boolean;
  }[];
}

let roughPromise: Promise<typeof import('roughjs/bin/rough').default> | null = null;
async function getRough() {
  if (!roughPromise) {
    roughPromise = import('roughjs/bin/rough').then((m) => m.default);
  }
  return roughPromise;
}

export async function renderDiagramCommand(cmd: BoardCommand): Promise<void> {
  const c = cmd as PrimitivesDiagram & NodeEdgeDiagram;
  const el = createElement('div', cmd, 'bd-diagram');
  const w = c.width ?? 480;
  const h = c.height ?? 320;
  el.style.minWidth = `${w}px`;
  el.style.minHeight = `${h}px`;
  placeElement(el, cmd.placement ?? 'below', cmd);

  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
  svg.setAttribute('width', `${w}`);
  svg.setAttribute('height', `${h}`);
  el.appendChild(svg);

  const isSketch = (c.style ?? 'sketch') === 'sketch';

  if (c.nodes || c.edges) {
    await renderNodesEdges(svg, c, isSketch);
  } else if (c.primitives) {
    if (isSketch) {
      const rough = await getRough();
      const rc = rough.svg(svg);
      for (const prim of c.primitives ?? []) {
        try {
          const drawn = drawPrimSketch(rc as unknown as SketchRc, prim);
          if (drawn) svg.appendChild(drawn);
        } catch {
          /* skip */
        }
      }
    } else {
      for (const prim of c.primitives ?? []) {
        const drawn = drawPrimCrisp(prim);
        if (drawn) svg.appendChild(drawn);
      }
    }
  }
}

async function renderNodesEdges(
  svg: SVGSVGElement,
  c: NodeEdgeDiagram,
  isSketch: boolean,
): Promise<void> {
  const NS = 'http://www.w3.org/2000/svg';
  const NODE_W = 120;
  const NODE_H = 56;
  const nodeMap = new Map<string, { x: number; y: number; w: number; h: number }>();

  const rough = isSketch ? (await getRough()).svg(svg) : null;

  // Edges first so they render under nodes.
  if (c.edges) {
    for (const edge of c.edges) {
      const from = c.nodes?.find((n) => n.id === edge.from);
      const to = c.nodes?.find((n) => n.id === edge.to);
      if (!from || !to) continue;
      const x1 = from.x + NODE_W / 2;
      const y1 = from.y + NODE_H / 2;
      const x2 = to.x + NODE_W / 2;
      const y2 = to.y + NODE_H / 2;
      if (rough) {
        svg.appendChild(rough.line(x1, y1, x2, y2));
      } else {
        const ln = document.createElementNS(NS, 'line');
        ln.setAttribute('x1', String(x1));
        ln.setAttribute('y1', String(y1));
        ln.setAttribute('x2', String(x2));
        ln.setAttribute('y2', String(y2));
        ln.setAttribute('stroke', '#5eead4');
        ln.setAttribute('stroke-width', '1.5');
        svg.appendChild(ln);
      }
      if (edge.arrow !== false) {
        const arrow = makeArrowHead(x2, y2, x1, y1);
        svg.appendChild(arrow);
      }
      if (edge.label) {
        const t = document.createElementNS(NS, 'text');
        t.setAttribute('x', String((x1 + x2) / 2));
        t.setAttribute('y', String((y1 + y2) / 2 - 6));
        t.setAttribute('fill', '#94a3b8');
        t.setAttribute('font-size', '12');
        t.setAttribute('text-anchor', 'middle');
        t.textContent = edge.label;
        svg.appendChild(t);
      }
    }
  }

  if (c.nodes) {
    for (const node of c.nodes) {
      nodeMap.set(node.id, { x: node.x, y: node.y, w: NODE_W, h: NODE_H });
      const shape = node.shape ?? 'rect';
      const stroke = node.color ?? '#5eead4';
      if (rough) {
        if (shape === 'circle' || shape === 'ellipse') {
          svg.appendChild(
            rough.ellipse(node.x + NODE_W / 2, node.y + NODE_H / 2, NODE_W, NODE_H, {
              stroke,
            }),
          );
        } else {
          svg.appendChild(
            rough.rectangle(node.x, node.y, NODE_W, NODE_H, { stroke }),
          );
        }
      } else {
        const r = document.createElementNS(NS, 'rect');
        r.setAttribute('x', String(node.x));
        r.setAttribute('y', String(node.y));
        r.setAttribute('width', String(NODE_W));
        r.setAttribute('height', String(NODE_H));
        r.setAttribute('rx', '6');
        r.setAttribute('fill', 'rgba(94,234,212,0.05)');
        r.setAttribute('stroke', stroke);
        r.setAttribute('stroke-width', '1.5');
        svg.appendChild(r);
      }
      if (node.label) {
        const t = document.createElementNS(NS, 'text');
        t.setAttribute('x', String(node.x + NODE_W / 2));
        t.setAttribute('y', String(node.y + NODE_H / 2 + 5));
        t.setAttribute('fill', '#ececec');
        t.setAttribute('font-size', '13');
        t.setAttribute('font-weight', '600');
        t.setAttribute('text-anchor', 'middle');
        t.textContent = node.label;
        svg.appendChild(t);
      }
    }
  }
}

function makeArrowHead(toX: number, toY: number, fromX: number, fromY: number): SVGElement {
  const NS = 'http://www.w3.org/2000/svg';
  const angle = Math.atan2(toY - fromY, toX - fromX);
  const headlen = 10;
  const x1 = toX - headlen * Math.cos(angle - Math.PI / 6);
  const y1 = toY - headlen * Math.sin(angle - Math.PI / 6);
  const x2 = toX - headlen * Math.cos(angle + Math.PI / 6);
  const y2 = toY - headlen * Math.sin(angle + Math.PI / 6);
  const path = document.createElementNS(NS, 'path');
  path.setAttribute('d', `M${toX},${toY} L${x1},${y1} L${x2},${y2} Z`);
  path.setAttribute('fill', '#5eead4');
  path.setAttribute('stroke', '#5eead4');
  return path;
}

interface SketchRc {
  line: (x1: number, y1: number, x2: number, y2: number) => SVGGElement;
  rectangle: (x: number, y: number, w: number, h: number) => SVGGElement;
  circle: (cx: number, cy: number, d: number) => SVGGElement;
}

function drawPrimSketch(
  rc: SketchRc,
  prim: { type: string; props: Record<string, unknown> },
): SVGElement | null {
  const p = prim.props as Record<string, number>;
  switch (prim.type) {
    case 'line':
      return rc.line(p.x1 ?? 0, p.y1 ?? 0, p.x2 ?? 0, p.y2 ?? 0);
    case 'rect':
    case 'box':
      return rc.rectangle(p.x ?? 0, p.y ?? 0, p.w ?? 10, p.h ?? 10);
    case 'circle':
      return rc.circle(p.cx ?? 0, p.cy ?? 0, p.r ?? 10);
    default:
      return null;
  }
}

function drawPrimCrisp(prim: { type: string; props: Record<string, unknown> }): SVGElement | null {
  const p = prim.props as Record<string, number | string>;
  const NS = 'http://www.w3.org/2000/svg';
  switch (prim.type) {
    case 'line': {
      const l = document.createElementNS(NS, 'line');
      l.setAttribute('x1', String(p.x1 ?? 0));
      l.setAttribute('y1', String(p.y1 ?? 0));
      l.setAttribute('x2', String(p.x2 ?? 0));
      l.setAttribute('y2', String(p.y2 ?? 0));
      l.setAttribute('stroke', String(p.color ?? '#5eead4'));
      l.setAttribute('stroke-width', '1.5');
      return l;
    }
    case 'rect':
    case 'box': {
      const r = document.createElementNS(NS, 'rect');
      r.setAttribute('x', String(p.x ?? 0));
      r.setAttribute('y', String(p.y ?? 0));
      r.setAttribute('width', String(p.w ?? 10));
      r.setAttribute('height', String(p.h ?? 10));
      r.setAttribute('fill', 'none');
      r.setAttribute('stroke', String(p.color ?? '#5eead4'));
      r.setAttribute('stroke-width', '1.5');
      return r;
    }
    case 'circle': {
      const c = document.createElementNS(NS, 'circle');
      c.setAttribute('cx', String(p.cx ?? 0));
      c.setAttribute('cy', String(p.cy ?? 0));
      c.setAttribute('r', String(p.r ?? 10));
      c.setAttribute('fill', 'none');
      c.setAttribute('stroke', String(p.color ?? '#5eead4'));
      c.setAttribute('stroke-width', '1.5');
      return c;
    }
    default:
      return null;
  }
}
