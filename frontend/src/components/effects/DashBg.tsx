import { useEffect, useRef } from 'react';

/**
 * Dashboard animated background — six science scenes (black hole, DNA helix,
 * quantum entanglement, atom shells, gravitational waves, Schrödinger packets,
 * orbital clouds) crossfading at the canvas edges. Native React port of
 * frontend-legacy/dash-bg.js.
 */

type Cloud = {
  bx: number;
  by: number;
  r: number;
  phase: number;
  speed: number;
  color: [number, number, number];
  type: 's' | 'p' | 'd';
};

interface Scene {
  clouds?: Cloud[] | null;
  init?: (W: number, H: number) => void;
  draw: (ctx: CanvasRenderingContext2D, W: number, H: number, t: number, a: number) => void;
}

const SCENE_DUR = 16;
const FADE_DUR = 5;

const scenes: Scene[] = [];

scenes.push({
  draw(ctx, W, H, t, a) {
    const cx = W * 0.06, cy = H * 0.08;
    const R = Math.min(W, H) * 0.22;
    for (let i = 0; i < 50; i++) {
      const ringR = R * (0.6 + i * 0.06);
      const squeeze = 0.28 + i * 0.003;
      const tilt = -0.25 + Math.sin(t * 0.15 + i * 0.1) * 0.05;
      const hue: [number, number, number] =
        i < 20 ? [255, 140 + i * 4, 60] : [200 - i * 2, 120 + i, 255];
      ctx.beginPath();
      ctx.ellipse(cx, cy, ringR, ringR * squeeze, tilt, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(${hue[0]},${hue[1]},${hue[2]},${(0.04 + (50 - i) * 0.002) * a})`;
      ctx.lineWidth = 1.2;
      ctx.stroke();
    }
    for (let i = 0; i < 120; i++) {
      const angle = (i / 120) * Math.PI * 2 + t * (0.25 + i * 0.001);
      const orbitR = R * (0.7 + 0.8 * ((i * 7.3) % 1));
      const squeeze = 0.3;
      const px = cx + Math.cos(angle) * orbitR;
      const py = cy + Math.sin(angle) * orbitR * squeeze;
      const bright = 0.4 + 0.6 * Math.abs(Math.sin(angle * 2 + t));
      const inner = orbitR < R * 1.2;
      ctx.beginPath();
      ctx.arc(px, py, inner ? 1.5 : 1, 0, Math.PI * 2);
      ctx.fillStyle = inner
        ? `rgba(255,200,100,${bright * 0.3 * a})`
        : `rgba(180,140,255,${bright * 0.15 * a})`;
      ctx.fill();
    }
    const bhg = ctx.createRadialGradient(cx, cy, R * 0.2, cx, cy, R * 0.55);
    bhg.addColorStop(0, `rgba(0,0,0,${0.95 * a})`);
    bhg.addColorStop(0.8, `rgba(0,0,0,${0.7 * a})`);
    bhg.addColorStop(1, 'rgba(10,13,11,0)');
    ctx.fillStyle = bhg;
    ctx.beginPath();
    ctx.arc(cx, cy, R * 0.55, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(cx, cy, R * 0.56, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(255,220,120,${0.2 * a})`;
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(cx, cy, R * 0.58, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(255,200,80,${0.08 * a})`;
    ctx.lineWidth = 4;
    ctx.stroke();
    for (const dir of [-1, 1]) {
      const grad = ctx.createLinearGradient(cx, cy, cx, cy + dir * R * 2.5);
      grad.addColorStop(0, `rgba(140,120,255,${0.12 * a})`);
      grad.addColorStop(1, 'rgba(140,120,255,0)');
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.moveTo(cx - 4, cy);
      ctx.lineTo(cx + 4, cy);
      ctx.lineTo(cx + 12, cy + dir * R * 2.5);
      ctx.lineTo(cx - 12, cy + dir * R * 2.5);
      ctx.closePath();
      ctx.fill();
    }
  },
});

scenes.push({
  draw(ctx, W, H, t, a) {
    const cx = W * 0.94;
    const top = -20, bot = H + 20;
    const radius = 45;
    const twist = 0.018;
    const rungs = 50;
    const strands = [
      { offset: 0, color: [52, 211, 153] as const },
      { offset: Math.PI, color: [94, 234, 212] as const },
    ];
    const pairColors: [readonly [number, number, number], readonly [number, number, number]][] = [
      [[255, 107, 107], [126, 184, 218]],
      [[245, 217, 122], [167, 139, 250]],
      [[126, 184, 218], [255, 107, 107]],
      [[167, 139, 250], [245, 217, 122]],
    ];
    for (let i = 0; i < rungs; i++) {
      const y = top + (i / rungs) * (bot - top);
      const phase = (y - top) * twist + t * 0.6;
      const x1 = cx + Math.sin(phase) * radius;
      const x2 = cx + Math.sin(phase + Math.PI) * radius;
      const depth = Math.cos(phase);
      const cols = pairColors[i % pairColors.length];
      ctx.beginPath();
      ctx.moveTo(x1, y);
      ctx.lineTo(x2, y);
      ctx.strokeStyle = `rgba(255,255,255,${(0.03 + Math.abs(depth) * 0.03) * a})`;
      ctx.lineWidth = 0.6;
      ctx.stroke();
      const dotR = 3 + depth;
      ctx.beginPath();
      ctx.arc(x1, y, Math.max(dotR, 1.5), 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${cols[0][0]},${cols[0][1]},${cols[0][2]},${(0.15 + depth * 0.1) * a})`;
      ctx.fill();
      ctx.beginPath();
      ctx.arc(x2, y, Math.max(3 - depth, 1.5), 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${cols[1][0]},${cols[1][1]},${cols[1][2]},${(0.15 - depth * 0.1) * a})`;
      ctx.fill();
    }
    for (const s of strands) {
      ctx.beginPath();
      for (let y = top; y <= bot; y += 2) {
        const phase = (y - top) * twist + t * 0.6 + s.offset;
        const x = cx + Math.sin(phase) * radius;
        if (y === top) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = `rgba(${s.color[0]},${s.color[1]},${s.color[2]},${0.22 * a})`;
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.strokeStyle = `rgba(${s.color[0]},${s.color[1]},${s.color[2]},${0.06 * a})`;
      ctx.lineWidth = 8;
      ctx.stroke();
    }
  },
});

scenes.push({
  draw(ctx, W, H, t, a) {
    const atomA = { x: W * 0.05, y: H * 0.88 };
    const atomB = { x: W * 0.95, y: H * 0.85 };
    for (let w = -3; w <= 3; w++) {
      const yOff = w * 8;
      ctx.beginPath();
      for (let i = 0; i <= 200; i++) {
        const frac = i / 200;
        const x = atomA.x + (atomB.x - atomA.x) * frac;
        const baseY = atomA.y + (atomB.y - atomA.y) * frac + yOff;
        const envelope = Math.sin(frac * Math.PI);
        const wave = Math.sin(frac * Math.PI * 12 + t * 2.5 + w * 0.5) * 15 * envelope;
        const y = baseY + wave;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = `rgba(167,139,250,${(0.04 + (3 - Math.abs(w)) * 0.015) * a})`;
      ctx.lineWidth = 1;
      ctx.stroke();
    }
    for (const atom of [atomA, atomB]) {
      const isA = atom === atomA;
      const cloudR = 55;
      const cg = ctx.createRadialGradient(atom.x, atom.y, 0, atom.x, atom.y, cloudR);
      cg.addColorStop(0, `rgba(167,139,250,${0.12 * a})`);
      cg.addColorStop(0.5, `rgba(167,139,250,${0.04 * a})`);
      cg.addColorStop(1, 'rgba(167,139,250,0)');
      ctx.fillStyle = cg;
      ctx.beginPath();
      ctx.arc(atom.x, atom.y, cloudR, 0, Math.PI * 2);
      ctx.fill();
      const spinAngle = isA ? t * 1.2 : t * 1.2 + Math.PI;
      const aLen = 28;
      const sx = atom.x, sy = atom.y;
      const ex = sx + Math.cos(spinAngle) * aLen;
      const ey = sy + Math.sin(spinAngle) * aLen;
      ctx.beginPath();
      ctx.moveTo(sx, sy);
      ctx.lineTo(ex, ey);
      ctx.strokeStyle = `rgba(94,234,212,${0.4 * a})`;
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(atom.x, atom.y, 5, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(167,139,250,${0.5 * a})`;
      ctx.fill();
    }
  },
});

scenes.push({
  draw(ctx, W, H, t, a) {
    const cx = W * 0.95, cy = H * 0.05;
    const ng = ctx.createRadialGradient(cx, cy, 0, cx, cy, 25);
    ng.addColorStop(0, `rgba(255,180,120,${0.15 * a})`);
    ng.addColorStop(1, 'rgba(255,180,120,0)');
    ctx.fillStyle = ng;
    ctx.beginPath();
    ctx.arc(cx, cy, 25, 0, Math.PI * 2);
    ctx.fill();
    const shells = [
      { r: 55, n: 2, speed: 1.0, color: [52, 211, 153] as const },
      { r: 95, n: 5, speed: -0.6, color: [94, 234, 212] as const },
      { r: 140, n: 7, speed: 0.35, color: [126, 184, 218] as const },
      { r: 190, n: 4, speed: -0.22, color: [167, 139, 250] as const },
    ];
    for (const sh of shells) {
      ctx.beginPath();
      ctx.arc(cx, cy, sh.r, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(${sh.color[0]},${sh.color[1]},${sh.color[2]},${0.08 * a})`;
      ctx.lineWidth = 0.8;
      ctx.stroke();
      for (let e = 0; e < sh.n; e++) {
        const angle = (e / sh.n) * Math.PI * 2 + t * sh.speed;
        const ex = cx + Math.cos(angle) * sh.r;
        const ey = cy + Math.sin(angle) * sh.r;
        ctx.beginPath();
        ctx.arc(ex, ey, 3, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${sh.color[0]},${sh.color[1]},${sh.color[2]},${0.6 * a})`;
        ctx.fill();
      }
    }
  },
});

scenes.push({
  draw(ctx, W, H, t, a) {
    const cx = W * 0.05, cy = H * 0.92;
    const orbitR = 20 + 5 * Math.sin(t * 0.2);
    for (const phase of [0, Math.PI]) {
      const mx = cx + Math.cos(t * 1.8 + phase) * orbitR;
      const my = cy + Math.sin(t * 1.8 + phase) * orbitR * 0.4;
      ctx.beginPath();
      ctx.arc(mx, my, 5, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(245,217,122,${0.5 * a})`;
      ctx.fill();
    }
    for (let i = 0; i < 18; i++) {
      const age = (t * 50 + i * 28) % 500;
      if (age > 400) continue;
      const r = age;
      const fade = 1 - age / 400;
      const squeeze = 0.35 + 0.08 * Math.sin(t * 3.6 + i);
      ctx.beginPath();
      ctx.ellipse(cx, cy, r, r * squeeze, 0, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(167,139,250,${fade * fade * 0.07 * a})`;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
  },
});

scenes.push({
  draw(ctx, W, H, t, a) {
    const baseX = 0, maxX = W * 0.18;
    const cy = H * 0.5;
    const packets = [
      { y: cy - 50, freq: 3, speed: 1.2, amp: 30, color: [52, 211, 153] as const },
      { y: cy, freq: 5, speed: -0.8, amp: 22, color: [94, 234, 212] as const },
      { y: cy + 50, freq: 2, speed: 0.6, amp: 35, color: [126, 184, 218] as const },
    ];
    for (const pk of packets) {
      ctx.beginPath();
      for (let x = baseX; x <= maxX; x += 2) {
        const nx = (x - baseX) / (maxX - baseX);
        const envelope = Math.pow(Math.sin(nx * Math.PI), 0.7);
        const val = envelope * pk.amp * Math.sin(nx * pk.freq * Math.PI * 2 + t * pk.speed);
        const y = pk.y + val;
        if (x === baseX) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = `rgba(${pk.color[0]},${pk.color[1]},${pk.color[2]},${0.2 * a})`;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
  },
});

// Scene 7 — orbital cloud chemistry. Stateful clouds initialized lazily.
scenes.push({
  clouds: null,
  init(W, H) {
    const N = 40;
    const out: Cloud[] = [];
    for (let i = 0; i < N; i++) {
      const types: Cloud['type'][] = ['s', 'p', 'd'];
      out.push({
        bx: Math.random() * W,
        by: Math.random() * H,
        r: 30 + Math.random() * 60,
        phase: Math.random() * Math.PI * 2,
        speed: 0.2 + Math.random() * 0.6,
        color: (Math.random() < 0.5
          ? [167, 139, 250]
          : Math.random() < 0.5
          ? [94, 234, 212]
          : [255, 180, 130]) as [number, number, number],
        type: types[i % 3],
      });
    }
    this.clouds = out;
  },
  draw(ctx, W, H, t, a) {
    if (!this.clouds) this.init?.(W, H);
    const clouds = this.clouds ?? [];
    for (const c of clouds) {
      const wob = Math.sin(t * c.speed + c.phase) * 8;
      const x = c.bx + wob;
      const y = c.by + Math.cos(t * c.speed * 0.8 + c.phase) * 6;
      const radius = c.r + Math.sin(t * c.speed + c.phase) * 4;
      const grad = ctx.createRadialGradient(x, y, 0, x, y, radius);
      grad.addColorStop(0, `rgba(${c.color[0]},${c.color[1]},${c.color[2]},${0.18 * a})`);
      grad.addColorStop(0.6, `rgba(${c.color[0]},${c.color[1]},${c.color[2]},${0.06 * a})`);
      grad.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = grad;
      ctx.beginPath();
      if (c.type === 'p') {
        // Bilobed shape — two overlapping ellipses
        ctx.ellipse(x - radius * 0.3, y, radius * 0.5, radius * 0.7, 0, 0, Math.PI * 2);
        ctx.ellipse(x + radius * 0.3, y, radius * 0.5, radius * 0.7, 0, 0, Math.PI * 2);
      } else if (c.type === 'd') {
        // Four-lobed shape — diagonal ellipses
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate(Math.PI / 4);
        ctx.ellipse(-radius * 0.35, 0, radius * 0.35, radius * 0.55, 0, 0, Math.PI * 2);
        ctx.ellipse(radius * 0.35, 0, radius * 0.35, radius * 0.55, 0, 0, Math.PI * 2);
        ctx.ellipse(0, -radius * 0.35, radius * 0.55, radius * 0.35, 0, 0, Math.PI * 2);
        ctx.ellipse(0, radius * 0.35, radius * 0.55, radius * 0.35, 0, 0, Math.PI * 2);
        ctx.restore();
      } else {
        ctx.arc(x, y, radius, 0, Math.PI * 2);
      }
      ctx.fill();
    }
  },
});

const TOTAL = scenes.length * (SCENE_DUR + FADE_DUR);

function alpha(idx: number, gt: number): number {
  const s = idx * (SCENE_DUR + FADE_DUR);
  const l = (((gt - s) % TOTAL) + TOTAL) % TOTAL;
  if (l < FADE_DUR) return l / FADE_DUR;
  if (l < FADE_DUR + SCENE_DUR) return 1;
  if (l < FADE_DUR * 2 + SCENE_DUR) return 1 - (l - FADE_DUR - SCENE_DUR) / FADE_DUR;
  return 0;
}

export function DashBg() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let t = 0;
    let rafId = 0;
    let W = 0;
    let H = 0;
    let dpr = 1;
    let running = true;

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = window.innerWidth;
      H = window.innerHeight;
      canvas.width = W * dpr;
      canvas.height = H * dpr;
      canvas.style.width = W + 'px';
      canvas.style.height = H + 'px';
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      for (const sc of scenes) {
        if (sc.init) sc.clouds = null;
      }
    };

    const frame = () => {
      if (!running) return;
      ctx.clearRect(0, 0, W, H);
      t += 1 / 60;
      for (let i = 0; i < scenes.length; i++) {
        const a2 = alpha(i, t) * 0.75;
        if (a2 < 0.005) continue;
        ctx.save();
        scenes[i].draw(ctx, W, H, t, a2);
        ctx.restore();
      }
      rafId = requestAnimationFrame(frame);
    };

    resize();
    window.addEventListener('resize', resize);
    rafId = requestAnimationFrame(frame);

    return () => {
      running = false;
      cancelAnimationFrame(rafId);
      window.removeEventListener('resize', resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 w-full h-full pointer-events-none -z-0 opacity-90"
      aria-hidden="true"
    />
  );
}
