/**
 * Animation Design System — Helper library injected before every p5.js animation.
 *
 * The tutor generates code that uses these helpers instead of raw p5.js.
 * Provides: color palette, drawing primitives, state management, smooth transitions.
 *
 * Usage in generated animation code:
 *   const A = new AnimHelper(p, W, H);
 *   A.state.particleX = 0.5;  // normalized 0-1
 *   A.animateTo('particleX', 0.8);  // smooth transition
 *
 * The tutor controls via anim-control:
 *   {"action":"set","param":"particleX","value":0.8}
 *   → calls A.animateTo('particleX', 0.8)
 */

class AnimHelper {
  constructor(p, W, H) {
    this.p = p;
    this.W = W;
    this.H = H;
    this.state = {};
    this._targets = {};
    this._t = 0;
    this._speed = 3; // lerp speed

    // ── Color palette ──
    this.colors = {
      bg: [10, 14, 26],
      bgPanel: [19, 26, 43],
      text: [241, 245, 249],
      textMuted: [148, 163, 184],
      accent: [59, 130, 246],    // blue
      accentAlt: [52, 211, 153], // green
      warm: [251, 191, 36],      // amber
      danger: [239, 68, 68],     // red
      purple: [167, 139, 250],
      pink: [244, 114, 182],
      cyan: [56, 189, 248],
      // Subject-specific
      positive: [52, 211, 153],
      negative: [239, 68, 68],
      neutral: [148, 163, 184],
    };
  }

  // ── State management ──

  /** Set initial state values */
  init(defaults) {
    for (const [k, v] of Object.entries(defaults)) {
      this.state[k] = v;
      this._targets[k] = v;
    }
  }

  /** Smoothly animate a state value to target */
  animateTo(key, value, speed) {
    this._targets[key] = value;
    if (speed !== undefined) this._speed = speed;
  }

  /** Set state instantly (no animation) */
  set(key, value) {
    this.state[key] = value;
    this._targets[key] = value;
  }

  /** Called by anim-control from tutor beats */
  _onControl(params) {
    if (params.action === 'set') {
      this.animateTo(params.param, params.value, params.speed);
    } else if (params.action === 'instant') {
      this.set(params.param, params.value);
    } else if (params.action === 'reset') {
      for (const k in this._targets) {
        this._targets[k] = this._defaults?.[k] ?? 0;
      }
    }
  }

  /** Call in draw() to update all animated values */
  tick() {
    const dt = Math.min(this.p.deltaTime / 1000, 0.05);
    this._t += dt;
    for (const k in this._targets) {
      const cur = this.state[k];
      const tgt = this._targets[k];
      if (typeof cur === 'number' && typeof tgt === 'number') {
        this.state[k] = cur + (tgt - cur) * Math.min(1, dt * this._speed);
      } else {
        this.state[k] = tgt;
      }
    }
  }

  // ── Drawing primitives ──

  /** Clear with dark background + subtle vignette */
  clear() {
    const p = this.p;
    p.background(10, 14, 26);
    // Subtle radial vignette
    p.noStroke();
    for (let i = 5; i > 0; i--) {
      const a = i * 3;
      p.fill(10, 14, 26, a);
      p.ellipse(this.W/2, this.H/2, this.W * (1 + i*0.15), this.H * (1 + i*0.15));
    }
  }

  /** Draw subtle grid */
  grid(spacing = 40, alpha = 12) {
    const p = this.p;
    p.stroke(148, 163, 184, alpha);
    p.strokeWeight(0.5);
    for (let x = 0; x < this.W; x += spacing) { p.line(x, 0, x, this.H); }
    for (let y = 0; y < this.H; y += spacing) { p.line(0, y, this.W, y); }
  }

  /** Draw a glowing circle */
  glow(x, y, r, color, intensity = 0.3) {
    const p = this.p;
    const [cr, cg, cb] = color;
    p.noStroke();
    // Outer glow layers
    for (let i = 4; i > 0; i--) {
      p.fill(cr, cg, cb, intensity * 255 / (i * 2));
      p.ellipse(x, y, r * (1 + i * 0.5), r * (1 + i * 0.5));
    }
    // Core
    p.fill(cr, cg, cb);
    p.ellipse(x, y, r, r);
  }

  /** Draw labeled point with glow */
  point(x, y, label, color, size = 16) {
    this.glow(x, y, size, color);
    if (label) {
      this.label(x, y + size/2 + 14, label, color, 11);
    }
  }

  /** Draw text label */
  label(x, y, text, color, size = 12, align = 'center') {
    const p = this.p;
    const [cr, cg, cb] = color || this.colors.text;
    p.fill(cr, cg, cb, 200);
    p.noStroke();
    p.textAlign(p[align.toUpperCase()] || p.CENTER, p.CENTER);
    p.textSize(size);
    p.textStyle(p.BOLD);
    p.text(text, x, y);
    p.textStyle(p.NORMAL);
  }

  /** Draw a title at top */
  title(text, y = 24) {
    this.label(this.W/2, y, text, this.colors.text, 15);
  }

  /** Draw annotation callout */
  callout(x, y, text, color, maxWidth = 180) {
    const p = this.p;
    const [cr, cg, cb] = color || this.colors.textMuted;
    const pad = 8;
    const lines = this._wrapText(text, maxWidth - pad*2);
    const h = lines.length * 16 + pad * 2;
    const w = maxWidth;

    // Background
    p.fill(10, 14, 26, 230);
    p.stroke(cr, cg, cb, 60);
    p.strokeWeight(1);
    p.rect(x - w/2, y, w, h, 6);

    // Text
    p.fill(cr, cg, cb, 180);
    p.noStroke();
    p.textSize(11);
    p.textAlign(p.CENTER, p.TOP);
    lines.forEach((line, i) => {
      p.text(line, x, y + pad + i * 16);
    });
  }

  _wrapText(text, maxW) {
    const words = text.split(' ');
    const lines = [];
    let line = '';
    for (const w of words) {
      const test = line ? line + ' ' + w : w;
      if (this.p.textWidth(test) > maxW && line) {
        lines.push(line);
        line = w;
      } else {
        line = test;
      }
    }
    if (line) lines.push(line);
    return lines;
  }

  /** Draw arrow */
  arrow(x1, y1, x2, y2, color, weight = 2) {
    const p = this.p;
    const [cr, cg, cb] = color;
    p.stroke(cr, cg, cb, 180);
    p.strokeWeight(weight);
    p.line(x1, y1, x2, y2);
    // Arrow head
    const angle = Math.atan2(y2 - y1, x2 - x1);
    const headLen = 8;
    p.fill(cr, cg, cb, 180);
    p.noStroke();
    p.triangle(
      x2, y2,
      x2 - headLen * Math.cos(angle - 0.4), y2 - headLen * Math.sin(angle - 0.4),
      x2 - headLen * Math.cos(angle + 0.4), y2 - headLen * Math.sin(angle + 0.4)
    );
  }

  /** Draw dashed line */
  dashed(x1, y1, x2, y2, color, dashLen = 6, gapLen = 4) {
    const p = this.p;
    const [cr, cg, cb] = color;
    p.stroke(cr, cg, cb, 100);
    p.strokeWeight(1);
    p.drawingContext.setLineDash([dashLen, gapLen]);
    p.line(x1, y1, x2, y2);
    p.drawingContext.setLineDash([]);
  }

  /** Draw filled region with border */
  region(x, y, w, h, fillColor, borderColor, alpha = 0.15) {
    const p = this.p;
    const [fr, fg, fb] = fillColor;
    const [br, bg, bb] = borderColor || fillColor;
    p.fill(fr, fg, fb, alpha * 255);
    p.stroke(br, bg, bb, 0.5 * 255);
    p.strokeWeight(1);
    p.rect(x, y, w, h, 4);
  }

  /** Draw a curve (array of [x,y] points) */
  curve(points, color, weight = 2, alpha = 1) {
    if (points.length < 2) return;
    const p = this.p;
    const [cr, cg, cb] = color;
    p.stroke(cr, cg, cb, alpha * 255);
    p.strokeWeight(weight);
    p.noFill();
    p.beginShape();
    points.forEach(([x, y]) => p.vertex(x, y));
    p.endShape();
  }

  /** Draw filled area under curve */
  filledCurve(points, baseY, color, alpha = 0.15) {
    if (points.length < 2) return;
    const p = this.p;
    const [cr, cg, cb] = color;
    p.fill(cr, cg, cb, alpha * 255);
    p.noStroke();
    p.beginShape();
    p.vertex(points[0][0], baseY);
    points.forEach(([x, y]) => p.vertex(x, y));
    p.vertex(points[points.length-1][0], baseY);
    p.endShape(p.CLOSE);
  }

  /** Draw a legend (top-right) */
  legend(items, x, y) {
    const p = this.p;
    const pad = 10;
    const lineH = 20;
    const w = 150;
    const h = items.length * lineH + pad * 2;

    // Background
    p.fill(10, 14, 26, 230);
    p.stroke(148, 163, 184, 30);
    p.strokeWeight(1);
    p.rect(x || (this.W - w - 12), y || 12, w, h, 8);

    // Items
    items.forEach((item, i) => {
      const ix = (x || (this.W - w - 12)) + pad;
      const iy = (y || 12) + pad + i * lineH + lineH / 2;
      const [cr, cg, cb] = item.color;
      p.fill(cr, cg, cb);
      p.noStroke();
      p.ellipse(ix + 4, iy, 8, 8);
      p.fill(226, 232, 240, 180);
      p.textSize(11);
      p.textAlign(p.LEFT, p.CENTER);
      p.text(item.label, ix + 16, iy);
    });
  }

  /** Draw equation box */
  equation(x, y, text, color) {
    const p = this.p;
    const [cr, cg, cb] = color || this.colors.accent;
    const w = Math.max(160, p.textWidth(text) + 30);
    p.fill(10, 14, 26, 230);
    p.stroke(cr, cg, cb, 60);
    p.strokeWeight(1);
    p.rect(x - w/2, y - 16, w, 32, 6);
    p.fill(cr, cg, cb);
    p.noStroke();
    p.textSize(14);
    p.textStyle(p.BOLD);
    p.textAlign(p.CENTER, p.CENTER);
    p.text(text, x, y);
    p.textStyle(p.NORMAL);
  }

  // ── Utility ──

  /** Normalized x (0-1) to pixel */
  nx(n) { return n * this.W; }
  /** Normalized y (0-1) to pixel */
  ny(n) { return n * this.H; }

  /** Fade alpha based on state value (0 = invisible, 1 = full) */
  fadeAlpha(stateKey) {
    return Math.max(0, Math.min(255, (this.state[stateKey] || 0) * 255));
  }

  /** Oscillate value between min and max */
  osc(freq = 1, min = 0, max = 1) {
    return min + (max - min) * (0.5 + 0.5 * Math.sin(this._t * freq * Math.PI * 2));
  }

  /** Pulse (0→1→0 over duration) */
  pulse(freq = 1) {
    return 0.5 + 0.5 * Math.sin(this._t * freq * Math.PI * 2);
  }
}

// Make available globally for p5.js instance mode
window.AnimHelper = AnimHelper;
