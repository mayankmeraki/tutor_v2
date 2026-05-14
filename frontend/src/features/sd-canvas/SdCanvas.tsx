import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { fabric } from 'fabric';
import { cn } from '@/components/ui/cn';

/**
 * System Design Canvas — Fabric-based whiteboard.
 * Native React port of frontend-legacy/sd-canvas.js core capabilities:
 * tools (select, pan, rect, diamond, ellipse, arrow, line, text, freehand),
 * pan (space + middle mouse + dedicated tool), pinch zoom, double-click
 * text edit / shape labeling, JSON sync, keyboard shortcuts, auto-return
 * to select after draw.
 */

export type SdTool =
  | 'select'
  | 'pan'
  | 'rect'
  | 'diamond'
  | 'ellipse'
  | 'arrow'
  | 'line'
  | 'text'
  | 'freehand';

const PALETTE = [
  { name: 'service', stroke: '#6C8EBF', fill: 'rgba(108,142,191,0.08)' },
  { name: 'database', stroke: '#82B366', fill: 'rgba(130,179,102,0.08)' },
  { name: 'cache', stroke: '#D6B656', fill: 'rgba(214,182,86,0.08)' },
  { name: 'client', stroke: '#B85450', fill: 'rgba(184,84,80,0.08)' },
  { name: 'external', stroke: '#9673A6', fill: 'rgba(150,115,166,0.08)' },
  { name: 'worker', stroke: '#D79B00', fill: 'rgba(215,155,0,0.08)' },
];
/** Brush color for freehand — legacy uses a fixed accent color. */
const FREEHAND_COLOR = PALETTE[0].stroke;

const MIN_DRAG = 8; // px — drags shorter than this are treated as clicks

export interface SdCanvasHandle {
  toJSON: () => unknown;
  loadJSON: (json: unknown) => void;
  clear: () => void;
  setTool: (tool: SdTool) => void;
  deleteSelection: () => void;
  zoomReset: () => void;
}

interface SdCanvasProps {
  className?: string;
  initialJSON?: unknown;
  onChange?: (json: unknown) => void;
}

export const SdCanvas = forwardRef<SdCanvasHandle, SdCanvasProps>(function SdCanvas(
  { className, initialJSON, onChange },
  ref,
) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasElRef = useRef<HTMLCanvasElement>(null);
  const fabricRef = useRef<fabric.Canvas | null>(null);
  const toolRef = useRef<SdTool>('select');
  const colorIdxRef = useRef(0);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const [tool, setToolState] = useState<SdTool>('select');

  useEffect(() => {
    const wrap = wrapRef.current;
    const el = canvasElRef.current;
    if (!wrap || !el) return;

    el.width = wrap.offsetWidth;
    el.height = wrap.offsetHeight;
    const canvas = new fabric.Canvas(el, {
      backgroundColor: 'transparent',
      selection: true,
      preserveObjectStacking: true,
    });
    fabric.Object.prototype.set({
      transparentCorners: false,
      cornerColor: 'rgba(108,142,191,0.6)',
      cornerStrokeColor: 'rgba(108,142,191,0.8)',
      cornerSize: 8,
      cornerStyle: 'circle',
      borderColor: 'rgba(108,142,191,0.4)',
      hasRotatingPoint: true,
    });
    fabricRef.current = canvas;

    if (initialJSON) {
      try {
        canvas.loadFromJSON(initialJSON, () => canvas.renderAll());
      } catch {
        /* ignore */
      }
    }

    const ro = new ResizeObserver(() => {
      canvas.setWidth(wrap.offsetWidth);
      canvas.setHeight(wrap.offsetHeight);
      canvas.renderAll();
    });
    ro.observe(wrap);

    let drawing = false;
    let start: { x: number; y: number } | null = null;
    let temp: fabric.Object | null = null;
    let spaceDown = false;
    let panning = false;
    let lastPan: { x: number; y: number } | null = null;

    const isInputFocused = () => {
      const t = document.activeElement as HTMLElement | null;
      if (!t) return false;
      const tag = t.tagName;
      return tag === 'INPUT' || tag === 'TEXTAREA' || t.isContentEditable;
    };

    const onKey = (e: KeyboardEvent) => {
      if (isInputFocused()) return;
      if (e.code === 'Space' && !spaceDown) {
        spaceDown = true;
        wrap.style.cursor = 'grab';
      }
      // Single-key shortcuts (legacy parity)
      if (!e.metaKey && !e.ctrlKey && !e.altKey) {
        const map: Record<string, SdTool> = {
          v: 'select',
          h: 'pan',
          r: 'rect',
          d: 'diamond',
          e: 'ellipse',
          a: 'arrow',
          l: 'line',
          t: 'text',
          f: 'freehand',
        };
        const tt = map[e.key.toLowerCase()];
        if (tt) {
          setToolState(tt);
          e.preventDefault();
        }
      }
      if (e.key === 'Delete' || e.key === 'Backspace') {
        const active = canvas.getActiveObject();
        if (active && !((active as fabric.IText).isEditing)) {
          e.preventDefault();
          canvas.getActiveObjects().forEach((o) => canvas.remove(o));
          canvas.discardActiveObject();
          canvas.requestRenderAll();
          onChangeRef.current?.(canvas.toJSON());
        }
      }
      if (e.key === 'Escape') {
        canvas.discardActiveObject();
        canvas.requestRenderAll();
      }
    };
    const onKeyUp = (e: KeyboardEvent) => {
      if (e.code === 'Space') {
        spaceDown = false;
        wrap.style.cursor = '';
      }
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('keyup', onKeyUp);

    canvas.on('mouse:down', (opt) => {
      const evt = opt.e as MouseEvent | TouchEvent;
      const isMiddle = evt instanceof MouseEvent && evt.button === 1;
      const wantPan = spaceDown || isMiddle || toolRef.current === 'pan';
      if (wantPan) {
        panning = true;
        const me = evt as MouseEvent;
        lastPan = { x: me.clientX, y: me.clientY };
        canvas.selection = false;
        wrap.style.cursor = 'grabbing';
        return;
      }
      if (toolRef.current === 'select') return;

      // If user mouse-downs on an existing shape (rect/diamond/ellipse/etc),
      // don't start drawing on top — let select pick it up.
      if (opt.target && toolRef.current !== 'text') {
        return;
      }

      const p = canvas.getPointer(opt.e);
      drawing = true;
      start = { x: p.x, y: p.y };
      const palette = PALETTE[colorIdxRef.current++ % PALETTE.length];

      switch (toolRef.current) {
        case 'rect':
          temp = new fabric.Rect({
            left: p.x,
            top: p.y,
            width: 1,
            height: 1,
            fill: palette.fill,
            stroke: palette.stroke,
            strokeWidth: 2,
            rx: 8,
            ry: 8,
          });
          break;
        case 'diamond':
          temp = new fabric.Polygon(
            [
              { x: 50, y: 0 },
              { x: 100, y: 50 },
              { x: 50, y: 100 },
              { x: 0, y: 50 },
            ],
            {
              left: p.x,
              top: p.y,
              fill: palette.fill,
              stroke: palette.stroke,
              strokeWidth: 2,
              scaleX: 0.01,
              scaleY: 0.01,
            },
          );
          break;
        case 'ellipse':
          temp = new fabric.Ellipse({
            left: p.x,
            top: p.y,
            rx: 1,
            ry: 1,
            fill: palette.fill,
            stroke: palette.stroke,
            strokeWidth: 2,
          });
          break;
        case 'line':
        case 'arrow':
          temp = new fabric.Line([p.x, p.y, p.x, p.y], {
            stroke: toolRef.current === 'arrow' ? 'rgba(148,163,184,0.6)' : palette.stroke,
            strokeWidth: 2,
            strokeDashArray: toolRef.current === 'arrow' ? [4, 4] : undefined,
          });
          break;
        case 'text': {
          const t = new fabric.IText('', {
            left: p.x,
            top: p.y,
            fill: palette.stroke,
            fontSize: 22,
            fontFamily: 'Inter',
            fontWeight: 600,
          });
          canvas.add(t);
          canvas.setActiveObject(t);
          t.enterEditing();
          drawing = false;
          temp = null;
          start = null;
          onChangeRef.current?.(canvas.toJSON());
          // Stay in text mode briefly; legacy returns to select after the click.
          setToolState('select');
          return;
        }
        case 'freehand':
          canvas.isDrawingMode = true;
          canvas.freeDrawingBrush.color = FREEHAND_COLOR;
          canvas.freeDrawingBrush.width = 2;
          drawing = false;
          return;
      }
      if (temp) canvas.add(temp);
    });

    canvas.on('mouse:move', (opt) => {
      if (panning && lastPan) {
        const me = opt.e as MouseEvent;
        const dx = me.clientX - lastPan.x;
        const dy = me.clientY - lastPan.y;
        const vp = canvas.viewportTransform!;
        vp[4] += dx;
        vp[5] += dy;
        canvas.requestRenderAll();
        lastPan = { x: me.clientX, y: me.clientY };
        return;
      }
      if (!drawing || !temp || !start) return;
      const p = canvas.getPointer(opt.e);
      switch (toolRef.current) {
        case 'rect':
          (temp as fabric.Rect).set({
            width: Math.abs(p.x - start.x),
            height: Math.abs(p.y - start.y),
            left: Math.min(p.x, start.x),
            top: Math.min(p.y, start.y),
          });
          break;
        case 'ellipse':
          (temp as fabric.Ellipse).set({
            rx: Math.abs(p.x - start.x) / 2,
            ry: Math.abs(p.y - start.y) / 2,
            left: Math.min(p.x, start.x),
            top: Math.min(p.y, start.y),
          });
          break;
        case 'diamond':
          temp.set({
            scaleX: Math.abs(p.x - start.x) / 100,
            scaleY: Math.abs(p.y - start.y) / 100,
            left: Math.min(p.x, start.x),
            top: Math.min(p.y, start.y),
          });
          break;
        case 'line':
        case 'arrow':
          (temp as fabric.Line).set({ x2: p.x, y2: p.y });
          break;
      }
      canvas.requestRenderAll();
    });

    canvas.on('mouse:up', () => {
      if (panning) {
        panning = false;
        lastPan = null;
        // Restore selection only if the active tool is select (or pan tool, which
        // re-enables selection after drag finishes).
        canvas.selection = toolRef.current === 'select';
        wrap.style.cursor = spaceDown || toolRef.current === 'pan' ? 'grab' : '';
      }
      if (drawing) {
        drawing = false;
        const finishedTool = toolRef.current;
        if (temp && start) {
          const p = (canvas as unknown as { _pointer?: { x: number; y: number } })._pointer;
          // Drop shapes that ended up smaller than MIN_DRAG.
          let tooSmall = false;
          if (finishedTool === 'rect' || finishedTool === 'ellipse' || finishedTool === 'diamond') {
            const w = (temp as fabric.Rect).width ?? 0;
            const h = (temp as fabric.Rect).height ?? 0;
            const sx = (temp as fabric.Object).scaleX ?? 1;
            const sy = (temp as fabric.Object).scaleY ?? 1;
            tooSmall = w * sx < MIN_DRAG && h * sy < MIN_DRAG;
          } else if (finishedTool === 'line' || finishedTool === 'arrow') {
            const ln = temp as fabric.Line;
            const dx = (ln.x2 ?? 0) - (ln.x1 ?? 0);
            const dy = (ln.y2 ?? 0) - (ln.y1 ?? 0);
            tooSmall = Math.hypot(dx, dy) < MIN_DRAG;
          }
          if (tooSmall) {
            canvas.remove(temp);
          } else {
            if (finishedTool === 'arrow') {
              const line = temp as fabric.Line;
              // Finalize arrow as solid (was dashed during preview)
              line.set({ stroke: 'rgba(148,163,184,0.6)', strokeDashArray: undefined });
              const head = makeArrowHead(
                line.x2 ?? 0,
                line.y2 ?? 0,
                line.x1 ?? 0,
                line.y1 ?? 0,
                line.stroke ?? '#fff',
              );
              canvas.add(head);
            }
            // Auto-return to select after a successful draw, legacy parity.
            setToolState('select');
          }
          // Suppress unused-variable hint for `p`.
          void p;
        }
        temp = null;
        start = null;
        onChangeRef.current?.(canvas.toJSON());
      }
    });

    // Double-click on a shape adds a centered label (legacy parity).
    canvas.on('mouse:dblclick', (opt) => {
      const target = opt.target;
      if (!target) return;
      if (target instanceof fabric.IText || target instanceof fabric.Textbox) return;
      const center = target.getCenterPoint();
      const t = new fabric.IText('label', {
        left: center.x,
        top: center.y,
        originX: 'center',
        originY: 'center',
        fill: '#ececec',
        fontSize: 16,
        fontFamily: 'Inter',
        fontWeight: 600,
      });
      canvas.add(t);
      canvas.setActiveObject(t);
      t.enterEditing();
      t.selectAll();
      onChangeRef.current?.(canvas.toJSON());
    });

    canvas.on('object:modified', () => onChangeRef.current?.(canvas.toJSON()));
    canvas.on('path:created', () => {
      canvas.isDrawingMode = false;
      onChangeRef.current?.(canvas.toJSON());
    });

    canvas.on('mouse:wheel', (opt) => {
      const evt = opt.e as WheelEvent;
      if (evt.ctrlKey || evt.metaKey) {
        evt.preventDefault();
        evt.stopPropagation();
        const delta = evt.deltaY;
        let zoom = canvas.getZoom();
        zoom *= 0.999 ** delta;
        zoom = Math.max(0.15, Math.min(zoom, 5));
        canvas.zoomToPoint({ x: evt.offsetX, y: evt.offsetY }, zoom);
      }
    });

    return () => {
      ro.disconnect();
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('keyup', onKeyUp);
      canvas.dispose();
      fabricRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    toolRef.current = tool;
    const canvas = fabricRef.current;
    if (!canvas) return;
    canvas.isDrawingMode = tool === 'freehand';
    canvas.selection = tool === 'select';
    if (tool === 'pan') {
      canvas.defaultCursor = 'grab';
    } else if (tool === 'select') {
      canvas.defaultCursor = 'default';
    } else {
      canvas.defaultCursor = 'crosshair';
    }
    // Lock objects while in non-select tools (legacy `_setObjectsSelectable`).
    canvas.forEachObject((o) => {
      o.selectable = tool === 'select';
      o.evented = tool === 'select' || tool === 'text';
    });
  }, [tool]);

  useImperativeHandle(
    ref,
    () => ({
      toJSON: () => fabricRef.current?.toJSON() ?? {},
      loadJSON: (json) => {
        fabricRef.current?.loadFromJSON(json, () =>
          fabricRef.current?.renderAll(),
        );
      },
      clear: () => {
        fabricRef.current?.clear();
        fabricRef.current?.setBackgroundColor('transparent', () => undefined);
        colorIdxRef.current = 0;
      },
      setTool: (t) => setToolState(t),
      deleteSelection: () => {
        const c = fabricRef.current;
        if (!c) return;
        c.getActiveObjects().forEach((o) => c.remove(o));
        c.discardActiveObject();
        c.requestRenderAll();
        onChangeRef.current?.(c.toJSON());
      },
      zoomReset: () => {
        fabricRef.current?.setZoom(1);
        fabricRef.current?.viewportTransform &&
          (fabricRef.current.viewportTransform = [1, 0, 0, 1, 0, 0]);
        fabricRef.current?.requestRenderAll();
      },
    }),
    [],
  );

  return (
    <div className={cn('relative w-full h-full', className)}>
      <Toolbar
        tool={tool}
        onChange={setToolState}
        onDelete={() => {
          const c = fabricRef.current;
          if (!c) return;
          c.getActiveObjects().forEach((o) => c.remove(o));
          c.discardActiveObject();
          c.requestRenderAll();
          onChangeRef.current?.(c.toJSON());
        }}
      />
      <div ref={wrapRef} className="w-full h-full">
        <canvas ref={canvasElRef} />
      </div>
    </div>
  );
});

function makeArrowHead(
  toX: number,
  toY: number,
  fromX: number,
  fromY: number,
  stroke: string,
): fabric.Object {
  const angle = Math.atan2(toY - fromY, toX - fromX);
  const headlen = 12;
  const tri = new fabric.Triangle({
    left: toX,
    top: toY,
    originX: 'center',
    originY: 'center',
    width: headlen,
    height: headlen,
    fill: stroke,
    angle: (angle * 180) / Math.PI + 90,
    selectable: false,
  });
  return tri;
}

const TOOLS: { id: SdTool; label: string; icon: string; key: string }[] = [
  { id: 'select', label: 'Select', icon: '⊡', key: 'V' },
  { id: 'pan', label: 'Pan', icon: '✋', key: 'H' },
  { id: 'rect', label: 'Rectangle', icon: '▭', key: 'R' },
  { id: 'diamond', label: 'Diamond', icon: '◇', key: 'D' },
  { id: 'ellipse', label: 'Ellipse', icon: '○', key: 'E' },
  { id: 'arrow', label: 'Arrow', icon: '→', key: 'A' },
  { id: 'line', label: 'Line', icon: '—', key: 'L' },
  { id: 'text', label: 'Text', icon: 'A', key: 'T' },
  { id: 'freehand', label: 'Draw', icon: '✎', key: 'F' },
];

function Toolbar({
  tool,
  onChange,
  onDelete,
}: {
  tool: SdTool;
  onChange: (t: SdTool) => void;
  onDelete: () => void;
}) {
  return (
    <div
      className="absolute top-3 left-3 z-10 bg-bg-elevated border border-border rounded-lg px-1 py-1 flex gap-0.5"
      data-testid="sd-canvas-toolbar"
    >
      {TOOLS.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => onChange(t.id)}
          className={cn(
            'h-7 min-w-[28px] px-2 text-xs rounded transition-colors',
            tool === t.id
              ? 'bg-accent text-bg'
              : 'text-text-muted hover:bg-bg-hover hover:text-text',
          )}
          title={`${t.label} (${t.key})`}
          data-testid={`sd-canvas-tool-${t.id}`}
        >
          {t.icon}
        </button>
      ))}
      <span className="w-px bg-border mx-1" />
      <button
        type="button"
        onClick={onDelete}
        className="h-7 min-w-[28px] px-2 text-xs rounded text-text-muted hover:bg-bad/15 hover:text-bad transition-colors"
        title="Delete selection (Del)"
        data-testid="sd-canvas-delete"
      >
        ✕
      </button>
    </div>
  );
}
