// ═══════════════════════════════════════════════════════════
// Dashboard Animated Background — Science Phenomena at Edges
// ═══════════════════════════════════════════════════════════

const DashBg = (() => {
  let canvas, ctx, W, H, dpr, t = 0, running = false, rafId = null;

  const SCENE_DUR = 16, FADE_DUR = 5;
  const scenes = [];

  // ── SCENE 1 — BLACK HOLE (top-left quadrant) ──────────────
  scenes.push({
    draw(ctx, W, H, t, a) {
      const cx = W * 0.06, cy = H * 0.08;
      const R = Math.min(W, H) * 0.22;

      // Warped accretion disk — elliptical rings with color gradient
      for (let i = 0; i < 50; i++) {
        const ringR = R * (0.6 + i * 0.06);
        const squeeze = 0.28 + i * 0.003;
        const tilt = -0.25 + Math.sin(t * 0.15 + i * 0.1) * 0.05;
        const hue = i < 20 ? [255, 140 + i * 4, 60] : [200 - i * 2, 120 + i, 255];
        ctx.beginPath();
        ctx.ellipse(cx, cy, ringR, ringR * squeeze, tilt, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${hue[0]},${hue[1]},${hue[2]},${(0.04 + (50 - i) * 0.002) * a})`;
        ctx.lineWidth = 1.2;
        ctx.stroke();
      }

      // Hot gas particles in disk
      for (let i = 0; i < 120; i++) {
        const angle = (i / 120) * Math.PI * 2 + t * (0.25 + i * 0.001);
        const orbitR = R * (0.7 + 0.8 * ((i * 7.3) % 1));
        const squeeze = 0.3;
        const px = cx + Math.cos(angle) * orbitR;
        const py = cy + Math.sin(angle) * orbitR * squeeze;
        const bright = 0.4 + 0.6 * Math.abs(Math.sin(angle * 2 + t));
        const inner = orbitR < R * 1.2;
        ctx.beginPath(); ctx.arc(px, py, inner ? 1.5 : 1, 0, Math.PI * 2);
        ctx.fillStyle = inner
          ? `rgba(255,200,100,${bright * 0.3 * a})`
          : `rgba(180,140,255,${bright * 0.15 * a})`;
        ctx.fill();
      }

      // Event horizon — deep black with sharp edge
      const bhg = ctx.createRadialGradient(cx, cy, R * 0.2, cx, cy, R * 0.55);
      bhg.addColorStop(0, `rgba(0,0,0,${0.95 * a})`);
      bhg.addColorStop(0.8, `rgba(0,0,0,${0.7 * a})`);
      bhg.addColorStop(1, 'rgba(10,13,11,0)');
      ctx.fillStyle = bhg;
      ctx.beginPath(); ctx.arc(cx, cy, R * 0.55, 0, Math.PI * 2); ctx.fill();

      // Photon ring
      ctx.beginPath(); ctx.arc(cx, cy, R * 0.56, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(255,220,120,${0.2 * a})`; ctx.lineWidth = 2; ctx.stroke();
      ctx.beginPath(); ctx.arc(cx, cy, R * 0.58, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(255,200,80,${0.08 * a})`; ctx.lineWidth = 4; ctx.stroke();

      // Relativistic jets (faint vertical beams)
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
    }
  });

  // ── SCENE 2 — DNA DOUBLE HELIX (right edge, full height) ──
  scenes.push({
    draw(ctx, W, H, t, a) {
      const cx = W * 0.94;
      const top = -20, bot = H + 20;
      const radius = 45;
      const twist = 0.018;
      const rungs = 50;
      const strands = [
        { offset: 0, color: [52, 211, 153] },
        { offset: Math.PI, color: [94, 234, 212] },
      ];
      const pairColors = [
        [[255, 107, 107], [126, 184, 218]],
        [[245, 217, 122], [167, 139, 250]],
        [[126, 184, 218], [255, 107, 107]],
        [[167, 139, 250], [245, 217, 122]],
      ];

      // Base pair rungs with hydrogen bonds
      for (let i = 0; i < rungs; i++) {
        const y = top + (i / rungs) * (bot - top);
        const phase = (y - top) * twist + t * 0.6;
        const x1 = cx + Math.sin(phase) * radius;
        const x2 = cx + Math.sin(phase + Math.PI) * radius;
        const depth = Math.cos(phase);
        const cols = pairColors[i % pairColors.length];

        // Rung line
        ctx.beginPath(); ctx.moveTo(x1, y); ctx.lineTo(x2, y);
        ctx.strokeStyle = `rgba(255,255,255,${(0.03 + Math.abs(depth) * 0.03) * a})`;
        ctx.lineWidth = 0.6; ctx.stroke();

        // Base pair dots at each end
        const dotR = 3 + depth;
        ctx.beginPath(); ctx.arc(x1, y, Math.max(dotR, 1.5), 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${cols[0].join(',')},${(0.15 + depth * 0.1) * a})`; ctx.fill();
        ctx.beginPath(); ctx.arc(x2, y, Math.max(3 - depth, 1.5), 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${cols[1].join(',')},${(0.15 - depth * 0.1) * a})`; ctx.fill();
      }

      // Backbone strands
      for (const s of strands) {
        ctx.beginPath();
        for (let y = top; y <= bot; y += 2) {
          const phase = (y - top) * twist + t * 0.6 + s.offset;
          const x = cx + Math.sin(phase) * radius;
          const depth = Math.cos(phase);
          ctx.lineWidth = 2 + depth;
          if (y === top) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.strokeStyle = `rgba(${s.color.join(',')},${0.22 * a})`;
        ctx.lineWidth = 2; ctx.stroke();

        // Sugar-phosphate glow along backbone
        ctx.strokeStyle = `rgba(${s.color.join(',')},${0.06 * a})`;
        ctx.lineWidth = 8; ctx.stroke();
      }
    }
  });

  // ── SCENE 3 — QUANTUM ENTANGLEMENT (bottom, spanning width) ──
  scenes.push({
    draw(ctx, W, H, t, a) {
      const atomA = { x: W * 0.05, y: H * 0.88 };
      const atomB = { x: W * 0.95, y: H * 0.85 };
      const midX = (atomA.x + atomB.x) / 2;
      const midY = (atomA.y + atomB.y) / 2;

      // Entanglement field — many parallel wavy connections
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
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.strokeStyle = `rgba(167,139,250,${(0.04 + (3 - Math.abs(w)) * 0.015) * a})`;
        ctx.lineWidth = 1; ctx.stroke();
      }

      // Traveling correlation pulses
      for (let p = 0; p < 3; p++) {
        const pos = ((t * 0.12 + p * 0.33) % 1);
        const px = atomA.x + (atomB.x - atomA.x) * pos;
        const py = atomA.y + (atomB.y - atomA.y) * pos +
          Math.sin(pos * Math.PI * 12 + t * 2.5) * 15 * Math.sin(pos * Math.PI);
        const pg = ctx.createRadialGradient(px, py, 0, px, py, 25);
        pg.addColorStop(0, `rgba(167,139,250,${0.3 * a})`);
        pg.addColorStop(1, 'rgba(167,139,250,0)');
        ctx.fillStyle = pg;
        ctx.beginPath(); ctx.arc(px, py, 25, 0, Math.PI * 2); ctx.fill();
      }

      // Both atoms
      for (const atom of [atomA, atomB]) {
        const isA = atom === atomA;

        // Probability cloud
        const cloudR = 55;
        const cg = ctx.createRadialGradient(atom.x, atom.y, 0, atom.x, atom.y, cloudR);
        cg.addColorStop(0, `rgba(167,139,250,${0.12 * a})`);
        cg.addColorStop(0.5, `rgba(167,139,250,${0.04 * a})`);
        cg.addColorStop(1, 'rgba(167,139,250,0)');
        ctx.fillStyle = cg;
        ctx.beginPath(); ctx.arc(atom.x, atom.y, cloudR, 0, Math.PI * 2); ctx.fill();

        // Spin arrow (entangled — always opposite)
        const spinAngle = isA ? t * 1.2 : t * 1.2 + Math.PI;
        const aLen = 28;
        const sx = atom.x, sy = atom.y;
        const ex = sx + Math.cos(spinAngle) * aLen;
        const ey = sy + Math.sin(spinAngle) * aLen;
        ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(ex, ey);
        ctx.strokeStyle = `rgba(94,234,212,${0.4 * a})`; ctx.lineWidth = 2; ctx.stroke();
        const ha = Math.atan2(ey - sy, ex - sx);
        ctx.beginPath();
        ctx.moveTo(ex, ey);
        ctx.lineTo(ex - 7 * Math.cos(ha - 0.4), ey - 7 * Math.sin(ha - 0.4));
        ctx.lineTo(ex - 7 * Math.cos(ha + 0.4), ey - 7 * Math.sin(ha + 0.4));
        ctx.closePath();
        ctx.fillStyle = `rgba(94,234,212,${0.4 * a})`; ctx.fill();

        // Orbiting ring
        ctx.beginPath();
        ctx.ellipse(atom.x, atom.y, 30, 12, t * 0.4 + (isA ? 0 : 1), 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(94,234,212,${0.1 * a})`; ctx.lineWidth = 0.8; ctx.stroke();

        // Core dot
        ctx.beginPath(); ctx.arc(atom.x, atom.y, 5, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(167,139,250,${0.5 * a})`; ctx.fill();

        // Label
        ctx.font = '12px -apple-system, sans-serif';
        ctx.fillStyle = `rgba(167,139,250,${0.12 * a})`;
        ctx.fillText(isA ? '|↑⟩' : '|↓⟩', atom.x - 8, atom.y - 45);
      }

      // Bell state equation
      ctx.font = '13px serif';
      ctx.fillStyle = `rgba(167,139,250,${0.06 * a})`;
      ctx.textAlign = 'center';
      ctx.fillText('|Φ⁺⟩ = (|↑↓⟩ + |↓↑⟩) / √2', midX, midY - 35);
      ctx.textAlign = 'start';
    }
  });

  // ── SCENE 4 — ATOM with full electron shells (top-right) ──
  scenes.push({
    draw(ctx, W, H, t, a) {
      const cx = W * 0.95, cy = H * 0.05;

      // Nucleus
      const nuc = 10;
      for (let i = 0; i < nuc; i++) {
        const ang = (i / nuc) * Math.PI * 2 + Math.sin(t * 0.4 + i) * 0.4;
        const r = 6 + Math.sin(t * 0.6 + i * 3) * 2;
        const nx = cx + Math.cos(ang) * r;
        const ny = cy + Math.sin(ang) * r;
        ctx.beginPath(); ctx.arc(nx, ny, 4, 0, Math.PI * 2);
        ctx.fillStyle = i % 2 === 0
          ? `rgba(255,107,107,${0.35 * a})`
          : `rgba(126,184,218,${0.3 * a})`;
        ctx.fill();
      }

      // Nucleus glow
      const ng = ctx.createRadialGradient(cx, cy, 0, cx, cy, 25);
      ng.addColorStop(0, `rgba(255,180,120,${0.15 * a})`);
      ng.addColorStop(1, 'rgba(255,180,120,0)');
      ctx.fillStyle = ng;
      ctx.beginPath(); ctx.arc(cx, cy, 25, 0, Math.PI * 2); ctx.fill();

      // Electron shells
      const shells = [
        { r: 55, n: 2, speed: 1.0, color: [52, 211, 153] },
        { r: 95, n: 5, speed: -0.6, color: [94, 234, 212] },
        { r: 140, n: 7, speed: 0.35, color: [126, 184, 218] },
        { r: 190, n: 4, speed: -0.22, color: [167, 139, 250] },
      ];

      for (const sh of shells) {
        // Shell orbital cloud
        ctx.beginPath(); ctx.arc(cx, cy, sh.r, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${sh.color.join(',')},${0.04 * a})`; ctx.lineWidth = 12; ctx.stroke();

        // Shell ring
        ctx.beginPath(); ctx.arc(cx, cy, sh.r, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${sh.color.join(',')},${0.08 * a})`; ctx.lineWidth = 0.8; ctx.stroke();

        // Electrons with trails
        for (let e = 0; e < sh.n; e++) {
          const angle = (e / sh.n) * Math.PI * 2 + t * sh.speed;
          const wobble = Math.sin(t * 1.5 + e * 7) * 4;
          const ex = cx + Math.cos(angle) * (sh.r + wobble);
          const ey = cy + Math.sin(angle) * (sh.r + wobble);

          // Comet trail
          ctx.beginPath();
          for (let s = 0; s < 25; s++) {
            const ta = angle - s * 0.04 * Math.sign(sh.speed);
            const tw = Math.sin(t * 1.5 + e * 7 - s * 0.08) * 4;
            const tx = cx + Math.cos(ta) * (sh.r + tw);
            const ty = cy + Math.sin(ta) * (sh.r + tw);
            if (s === 0) ctx.moveTo(tx, ty); else ctx.lineTo(tx, ty);
          }
          ctx.strokeStyle = `rgba(${sh.color.join(',')},${0.12 * a})`;
          ctx.lineWidth = 1.5; ctx.stroke();

          // Electron
          ctx.beginPath(); ctx.arc(ex, ey, 3, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${sh.color.join(',')},${0.6 * a})`; ctx.fill();

          // Glow
          const eg = ctx.createRadialGradient(ex, ey, 0, ex, ey, 12);
          eg.addColorStop(0, `rgba(${sh.color.join(',')},${0.2 * a})`);
          eg.addColorStop(1, `rgba(${sh.color.join(',')},0)`);
          ctx.fillStyle = eg;
          ctx.beginPath(); ctx.arc(ex, ey, 12, 0, Math.PI * 2); ctx.fill();
        }
      }
    }
  });

  // ── SCENE 5 — GRAVITATIONAL WAVES / BINARY MERGER (bottom-left) ──
  scenes.push({
    draw(ctx, W, H, t, a) {
      const cx = W * 0.05, cy = H * 0.92;

      // Binary orbit (spiraling in)
      const orbitR = 20 + 5 * Math.sin(t * 0.2);
      for (const phase of [0, Math.PI]) {
        const mx = cx + Math.cos(t * 1.8 + phase) * orbitR;
        const my = cy + Math.sin(t * 1.8 + phase) * orbitR * 0.4;
        ctx.beginPath(); ctx.arc(mx, my, 5, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(245,217,122,${0.5 * a})`; ctx.fill();
        const mg = ctx.createRadialGradient(mx, my, 0, mx, my, 15);
        mg.addColorStop(0, `rgba(245,217,122,${0.15 * a})`);
        mg.addColorStop(1, 'rgba(245,217,122,0)');
        ctx.fillStyle = mg;
        ctx.beginPath(); ctx.arc(mx, my, 15, 0, Math.PI * 2); ctx.fill();
      }

      // Expanding wavefronts
      for (let i = 0; i < 18; i++) {
        const age = (t * 50 + i * 28) % 500;
        if (age > 400) continue;
        const r = age;
        const fade = (1 - age / 400);
        const squeeze = 0.35 + 0.08 * Math.sin(t * 3.6 + i);
        ctx.beginPath();
        ctx.ellipse(cx, cy, r, r * squeeze, 0, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(167,139,250,${fade * fade * 0.07 * a})`;
        ctx.lineWidth = 1.5; ctx.stroke();
      }

      // Spacetime fabric grid distortion
      const gs = 30, ext = 300;
      ctx.strokeStyle = `rgba(255,255,255,${0.018 * a})`; ctx.lineWidth = 0.4;
      for (let gx = cx - ext; gx <= cx + ext; gx += gs) {
        ctx.beginPath();
        for (let gy = cy - ext * 0.4; gy <= cy + ext * 0.2; gy += 4) {
          const dx = gx - cx, dy = gy - cy;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const wave = Math.sin(dist * 0.04 - t * 1.8) * 12 * Math.exp(-dist * 0.005);
          ctx.lineTo(gx + wave * dx / dist * 0.3, gy + wave * dy / dist * 0.15);
        }
        ctx.stroke();
      }
      for (let gy = cy - ext * 0.4; gy <= cy + ext * 0.2; gy += gs) {
        ctx.beginPath();
        for (let gx = cx - ext; gx <= cx + ext; gx += 4) {
          const dx = gx - cx, dy = gy - cy;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const wave = Math.sin(dist * 0.04 - t * 1.8) * 12 * Math.exp(-dist * 0.005);
          ctx.lineTo(gx + wave * dx / dist * 0.3, gy + wave * dy / dist * 0.15);
        }
        ctx.stroke();
      }
    }
  });

  // ── SCENE 6 — SCHRÖDINGER WAVE EQUATION (left edge, mid) ──
  scenes.push({
    draw(ctx, W, H, t, a) {
      const baseX = 0, maxX = W * 0.18;
      const cy = H * 0.5;

      // Multiple propagating wave packets
      const packets = [
        { y: cy - 50, freq: 3, speed: 1.2, amp: 30, color: [52, 211, 153] },
        { y: cy,      freq: 5, speed: -0.8, amp: 22, color: [94, 234, 212] },
        { y: cy + 50, freq: 2, speed: 0.6, amp: 35, color: [126, 184, 218] },
      ];

      for (const pk of packets) {
        // ψ(x,t) wave
        ctx.beginPath();
        for (let x = baseX; x <= maxX; x += 2) {
          const nx = (x - baseX) / (maxX - baseX);
          const envelope = Math.pow(Math.sin(nx * Math.PI), 0.7);
          const val = envelope * pk.amp * Math.sin(nx * pk.freq * Math.PI * 2 + t * pk.speed);
          const y = pk.y + val;
          if (x === baseX) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.strokeStyle = `rgba(${pk.color.join(',')},${0.2 * a})`;
        ctx.lineWidth = 1.5; ctx.stroke();

        // |ψ|² probability fill
        ctx.beginPath();
        ctx.moveTo(baseX, pk.y + pk.amp + 5);
        for (let x = baseX; x <= maxX; x += 2) {
          const nx = (x - baseX) / (maxX - baseX);
          const envelope = Math.pow(Math.sin(nx * Math.PI), 0.7);
          const val = envelope * Math.sin(nx * pk.freq * Math.PI * 2 + t * pk.speed);
          ctx.lineTo(x, pk.y + pk.amp + 5 - val * val * pk.amp * 0.6);
        }
        ctx.lineTo(maxX, pk.y + pk.amp + 5);
        ctx.closePath();
        ctx.fillStyle = `rgba(${pk.color.join(',')},${0.04 * a})`;
        ctx.fill();
      }

      // Floating symbols
      ctx.font = '28px serif';
      ctx.fillStyle = `rgba(52,211,153,${0.05 * a})`;
      ctx.fillText('ψ', 20 + Math.sin(t * 0.3) * 8, H * 0.32);
      ctx.font = '18px serif';
      ctx.fillStyle = `rgba(94,234,212,${0.04 * a})`;
      ctx.fillText('ℏ', 50 + Math.cos(t * 0.25) * 6, H * 0.65);
      ctx.font = '14px serif';
      ctx.fillStyle = `rgba(126,184,218,${0.04 * a})`;
      ctx.fillText('∇²ψ', 10 + Math.sin(t * 0.2) * 5, H * 0.45);
    }
  });

  // ── SCENE 7 — ORBITAL CLOUDS / CHEMISTRY (bottom-right) ──
  scenes.push({
    clouds: null,
    init(W, H) {
      this.clouds = [];
      const cx = W * 0.92, cy = H * 0.88;
      // s-orbital (sphere)
      for (let i = 0; i < 150; i++) {
        const a2 = Math.random() * Math.PI * 2;
        const r = Math.random() * 30;
        this.clouds.push({
          bx: cx + Math.cos(a2) * r, by: cy + Math.sin(a2) * r,
          r: 0.8 + Math.random() * 1.2,
          phase: Math.random() * Math.PI * 2, speed: 0.2 + Math.random() * 0.4,
          color: [52, 211, 153], type: 's',
        });
      }
      // p-orbital (two lobes along y)
      for (let i = 0; i < 200; i++) {
        const lobe = Math.random() < 0.5 ? -1 : 1;
        const r = Math.pow(Math.random(), 0.7) * 70;
        const spread = (Math.random() - 0.5) * 30;
        this.clouds.push({
          bx: cx + spread, by: cy + lobe * (25 + r * 0.6),
          r: 0.6 + Math.random() * 1,
          phase: Math.random() * Math.PI * 2, speed: 0.15 + Math.random() * 0.3,
          color: lobe > 0 ? [167, 139, 250] : [126, 184, 218], type: 'p',
        });
      }
      // d-orbital (four lobes, diagonal)
      for (let i = 0; i < 160; i++) {
        const quad = Math.floor(Math.random() * 4);
        const angles = [0.6, 2.2, 3.7, 5.3];
        const a2 = angles[quad] + (Math.random() - 0.5) * 0.8;
        const r = Math.pow(Math.random(), 0.6) * 55;
        this.clouds.push({
          bx: cx + Math.cos(a2) * (40 + r), by: cy + Math.sin(a2) * (25 + r * 0.6),
          r: 0.5 + Math.random() * 0.8,
          phase: Math.random() * Math.PI * 2, speed: 0.1 + Math.random() * 0.2,
          color: [245, 217, 122], type: 'd',
        });
      }
    },
    draw(ctx, W, H, t, a) {
      if (!this.clouds) this.init(W, H);
      const cx = W * 0.92, cy = H * 0.88;

      // Nucleus
      ctx.beginPath(); ctx.arc(cx, cy, 4, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(255,200,100,${0.4 * a})`; ctx.fill();

      // Cross-section axes
      ctx.strokeStyle = `rgba(255,255,255,${0.02 * a})`; ctx.lineWidth = 0.5;
      ctx.beginPath(); ctx.moveTo(cx - 100, cy); ctx.lineTo(cx + 100, cy); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(cx, cy - 100); ctx.lineTo(cx, cy + 100); ctx.stroke();

      // Draw all cloud dots
      for (const p of this.clouds) {
        const dx = Math.sin(t * p.speed + p.phase) * 4;
        const dy = Math.cos(t * p.speed * 0.8 + p.phase + 1) * 3;
        const pulse = 0.3 + 0.4 * Math.sin(t * 0.8 + p.phase);
        ctx.beginPath();
        ctx.arc(p.bx + dx, p.by + dy, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${p.color.join(',')},${pulse * 0.15 * a})`;
        ctx.fill();
      }

      // Labels
      ctx.font = '9px -apple-system, sans-serif';
      ctx.fillStyle = `rgba(52,211,153,${0.06 * a})`;
      ctx.fillText('1s', cx - 5, cy + 3);
      ctx.fillStyle = `rgba(167,139,250,${0.06 * a})`;
      ctx.fillText('2p', cx - 3, cy - 50);
      ctx.fillStyle = `rgba(245,217,122,${0.06 * a})`;
      ctx.fillText('3d', cx + 55, cy - 30);
    }
  });

  // ── Scene manager ──
  const TOTAL = scenes.length * (SCENE_DUR + FADE_DUR);

  function alpha(idx, gt) {
    const s = idx * (SCENE_DUR + FADE_DUR);
    const l = ((gt - s) % TOTAL + TOTAL) % TOTAL;
    if (l < FADE_DUR) return l / FADE_DUR;
    if (l < FADE_DUR + SCENE_DUR) return 1;
    if (l < FADE_DUR * 2 + SCENE_DUR) return 1 - (l - FADE_DUR - SCENE_DUR) / FADE_DUR;
    return 0;
  }

  function frame() {
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
  }

  function resize() {
    if (!canvas) return;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = window.innerWidth; H = window.innerHeight;
    canvas.width = W * dpr; canvas.height = H * dpr;
    canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    // Reinit stateful scenes on resize
    for (const sc of scenes) { if (sc.init) sc.clouds = null; }
  }

  return {
    start() {
      if (running) return;
      canvas = document.getElementById('dash-bg-canvas');
      if (!canvas) return;
      ctx = canvas.getContext('2d');
      running = true;
      document.body.classList.add('dash-bg-active');
      resize();
      window.addEventListener('resize', resize);
      rafId = requestAnimationFrame(frame);
    },
    stop() {
      if (!running) return;
      running = false;
      if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
      window.removeEventListener('resize', resize);
      document.body.classList.remove('dash-bg-active');
      if (canvas && ctx) ctx.clearRect(0, 0, W, H);
    }
  };
})();
