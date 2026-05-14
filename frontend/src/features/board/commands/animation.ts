/**
 * Animation — p5.js integration for inline board animations.
 * Native TypeScript port of frontend-legacy/board/animation.js.
 */

import p5 from 'p5';
import { board, type BoardCommand } from '../engine/state';
import { createElement } from '../engine/renderer';
import { placeElement } from '../engine/placement';

function sanitizeCode(input: string): string {
  let code = input;
  code = code.replace(/[\u2018\u2019\u201A\u2032]/g, "'");
  code = code.replace(/[\u201C\u201D\u201E\u2033]/g, '"');
  code = code.replace(/[\u2013\u2014\u2212]/g, '-');
  code = code.replace(/[\u200B\u200C\u200D\uFEFF]/g, '');
  code = code.replace(/\u00D7/g, '*');
  code = code.replace(/\u00F7/g, '/');
  code = code.replace(/\u2264/g, '<=');
  code = code.replace(/\u2265/g, '>=');
  code = code.replace(/\u2260/g, '!=');
  code = code.replace(/\u03C0/g, 'Math.PI');
  code = code.replace(/\u00A0/g, ' ');
  code = code.replace(/^```(?:javascript|js)?\s*/i, '').replace(/\s*```\s*$/, '');

  const stack: string[] = [];
  let strChar: string | null = null;
  let esc = false;
  let inLineComment = false;
  let inBlockComment = false;
  for (let i = 0; i < code.length; i++) {
    const ch = code[i];
    const next = code[i + 1];
    if (inLineComment) {
      if (ch === '\n') inLineComment = false;
      continue;
    }
    if (inBlockComment) {
      if (ch === '*' && next === '/') {
        inBlockComment = false;
        i++;
      }
      continue;
    }
    if (esc) {
      esc = false;
      continue;
    }
    if (strChar) {
      if (ch === '\\') {
        esc = true;
        continue;
      }
      if (ch === strChar) strChar = null;
      continue;
    }
    if (ch === '/' && next === '/') {
      inLineComment = true;
      i++;
      continue;
    }
    if (ch === '/' && next === '*') {
      inBlockComment = true;
      i++;
      continue;
    }
    if (ch === "'" || ch === '"' || ch === '`') {
      strChar = ch;
      continue;
    }
    if (ch === '{') stack.push('}');
    else if (ch === '(') stack.push(')');
    else if (ch === '[') stack.push(']');
    else if (ch === '}' || ch === ')' || ch === ']') stack.pop();
  }
  if (stack.length) code += stack.reverse().join('');

  code = code.replace(/\b(let|const|var)\s+(W|H)\b\s*=/g, '$2 =');
  code = code.replace(/\b(let|const|var)\s+S\b\s*=/g, 'S =');
  code = code.replace(/\bp\.background\s*\([^;)]*(?:\([^)]*\)[^;)]*)*\)/g, 'p.clear()');
  code = code.replace(/(?<![\w.])background\s*\([^;)]*(?:\([^)]*\)[^;)]*)*\)/g, 'p.clear()');
  return code;
}

function buildControlBridge(scale: number, isWebGL: boolean): string {
  return `
    var _controlParams = {};
    var S = ${scale.toFixed(2)};
    function onControl(params) {
      if (params._unhighlight) { _controlParams._highlight = null; }
      Object.assign(_controlParams, params);
      if (p._animHelper && p._animHelper._onControl) { p._animHelper._onControl(params); }
    }
    p._onControl = function(params) { onControl(params); };
    function sTextSize(sz) { return sz * S; }
    function sStroke(w) { return Math.max(1, w * S); }
    function applyHighlight(p, color, isHighlighted) {
      if (isHighlighted) { p.strokeWeight(sStroke(3)); p.drawingContext.shadowColor = color || '#34d399'; p.drawingContext.shadowBlur = 18 * S; }
      else { p.strokeWeight(sStroke(1.5)); p.drawingContext.shadowBlur = 0; }
    }
    ['setLineDash','getLineDash','setTransform','resetTransform','clip','clearRect',
     'createLinearGradient','createRadialGradient','measureText','fillRect','strokeRect'].forEach(function(m) {
      if (!p[m] && p.drawingContext && typeof p.drawingContext[m] === 'function') {
        p[m] = function() { return p.drawingContext[m].apply(p.drawingContext, arguments); };
      }
    });
    p._origTextFont = p.textFont;
    p.textFont = function() {};
    ${isWebGL ? `
    p.text = function() {};
    p.textSize = function() {};
    p.textAlign = function() {};
    ` : ''}
  `;
}

export async function createAnimation(cmd: BoardCommand): Promise<void> {
  const code = (cmd as { code?: string }).code;
  if (!code) return;

  const el = createElement('div', cmd, 'bd-anim-box');
  const controls = document.createElement('div');
  controls.className = 'bd-anim-controls';
  el.appendChild(controls);

  const canvasWrap = document.createElement('div');
  canvasWrap.className = 'bd-anim-canvas-wrap';
  el.appendChild(canvasWrap);

  placeElement(el, cmd.placement, cmd);

  const elRect = el.getBoundingClientRect();
  const pw = Math.round(elRect.width) || 300;
  const ph = Math.round(elRect.height) || 200;

  const isWebGL = /p\.WEBGL|,\s*WEBGL/.test(code);
  const scale = pw / 300;
  let processed = sanitizeCode(code);
  processed = processed.replace(/p\.textSize\((\d+(?:\.\d+)?)\)/g, (_, n) => `p.textSize(${n} * S)`);
  processed = processed.replace(
    /p\.strokeWeight\((\d+(?:\.\d+)?)\)/g,
    (_, n) => `p.strokeWeight(Math.max(1, ${n} * S))`,
  );
  const fullCode = buildControlBridge(scale, isWebGL) + '\n' + processed;

  let sketchFn: (p: p5, W: number, H: number) => void;
  try {
    // eslint-disable-next-line @typescript-eslint/no-implied-eval, no-new-func
    sketchFn = new Function('p', 'W', 'H', fullCode) as typeof sketchFn;
  } catch {
    canvasWrap.innerHTML =
      '<div style="padding:12px;color:rgba(248,113,113,0.4);font-size:12px;font-family:monospace">Animation compile error</div>';
    return;
  }

  let inst: p5;
  try {
    inst = new p5((p) => {
      try {
        sketchFn(p, pw, ph);
      } catch {
        canvasWrap.innerHTML =
          '<div style="padding:12px;color:rgba(248,113,113,0.4);font-size:12px;font-family:monospace">Animation error</div>';
        return;
      }
      const proxy = p as p5 & {
        _origTextFont?: (...args: unknown[]) => unknown;
        _animHelper?: unknown;
        _renderer?: { isP3D?: boolean };
      };
      const userDraw = p.draw;
      if (userDraw) {
        let errors = 0;
        p.draw = function () {
          try {
            userDraw.call(p);
          } catch {
            if (++errors >= 30) p.noLoop();
          }
        };
      }
      const userSetup = p.setup;
      p.setup = function () {
        if (userSetup) userSetup.call(p);
        try {
          if (!proxy._renderer?.isP3D) {
            (proxy._origTextFont as ((font: string) => unknown) | undefined)?.call(p, 'Lexend');
          }
        } catch {
          /* ignore */
        }
      };
    }, canvasWrap);
  } catch {
    canvasWrap.innerHTML =
      '<div style="padding:12px;color:rgba(248,113,113,0.4);font-size:12px">Init error</div>';
    return;
  }

  (el as HTMLElement & { _p5Instance?: p5 })._p5Instance = inst;
  board.animations.push({
    container: el,
    instance: {
      remove: () => inst.remove(),
      loop: () => inst.loop(),
      noLoop: () => inst.noLoop(),
      redraw: () => inst.redraw(),
    },
    _running: true,
  });
}
