#!/usr/bin/env node
/**
 * Focused animation rendering test.
 *
 * Goal: Verify that when the tutor is asked to teach a visual topic,
 * the animation actually renders (non-blank canvas, visible content).
 *
 * Flow:
 *   1. Login
 *   2. Send one of several "visual topic" prompts
 *   3. Wait for tutor to finish the first few beats
 *   4. Inspect every animation canvas on the board — check that it has
 *      been drawn to (center pixel is not transparent/black background)
 *   5. Capture console errors and warnings
 *   6. Screenshot the board
 *   7. Report pass/fail with details
 *
 * Usage:
 *   node animation-test.js
 *   node animation-test.js --topic "teach me how DNA replication works"
 *   HEADED=1 node animation-test.js
 */

import { chromium } from 'playwright';
import { CONFIG } from './config.js';
import { existsSync, mkdirSync, writeFileSync } from 'fs';

// Visual topics that should definitely generate animations.
// Ordered from simplest (neural network — flat diagram) to richest (DNA).
const VISUAL_TOPICS = [
  'teach me how a neural network makes a prediction — just the forward pass',
  'teach me the structure of DNA double helix',
  'teach me how an electromagnetic wave propagates through space',
];

async function main() {
  const args = process.argv.slice(2);
  let customTopic = null;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--topic' && args[i + 1]) { customTopic = args[i + 1]; i++; }
  }

  const topics = customTopic ? [customTopic] : VISUAL_TOPICS;
  if (!existsSync(CONFIG.outputDir)) mkdirSync(CONFIG.outputDir, { recursive: true });

  const results = [];
  for (const topic of topics) {
    console.log(`\n${'═'.repeat(70)}`);
    console.log(`TOPIC: ${topic}`);
    console.log('═'.repeat(70));
    const result = await runAnimationTest(topic);
    results.push(result);
  }

  // Summary
  console.log(`\n${'═'.repeat(70)}`);
  console.log('SUMMARY');
  console.log('═'.repeat(70));
  for (const r of results) {
    const status = r.pass ? '✓ PASS' : '✗ FAIL';
    console.log(`${status} — ${r.topic.slice(0, 55)}`);
    console.log(`       animations: ${r.animationCount}, rendered: ${r.renderedCount}, errors: ${r.errorCount}`);
    if (r.issues.length > 0) {
      for (const issue of r.issues) console.log(`       - ${issue}`);
    }
  }

  const allPass = results.every(r => r.pass);
  console.log(`\n${allPass ? '✓ ALL PASSED' : '✗ SOME FAILED'}`);
  process.exit(allPass ? 0 : 1);
}

async function runAnimationTest(topic) {
  const browser = await chromium.launch({
    headless: !CONFIG.headed,
    slowMo: CONFIG.slowMo,
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  const consoleMessages = [];
  const pageErrors = [];
  page.on('console', msg => {
    const text = msg.text();
    consoleMessages.push({ type: msg.type(), text });
    if (msg.type() === 'error' || msg.type() === 'warning') {
      console.log(`  [browser ${msg.type()}] ${text.slice(0, 150)}`);
    }
  });
  page.on('pageerror', err => {
    pageErrors.push(err.message);
    console.log(`  [page error] ${err.message}`);
  });

  const result = {
    topic,
    pass: false,
    animationCount: 0,
    renderedCount: 0,
    errorCount: 0,
    issues: [],
    consoleSample: [],
  };

  try {
    // Login
    console.log('[Test] Logging in...');
    await page.goto(`${CONFIG.baseUrl}/login`);
    await page.waitForSelector('#login-email', { timeout: 10_000 });
    await page.fill('#login-email', CONFIG.email);
    await page.fill('#login-password', CONFIG.password);
    await page.click('#btn-login');
    await page.waitForURL('**/home', { timeout: 15_000 });
    console.log('[Test] Logged in');

    // Wait for home screen
    await page.waitForSelector('#euler-input', { timeout: 10_000 });
    await page.waitForTimeout(1500);

    // Send topic
    console.log(`[Test] Sending topic...`);
    await page.fill('#euler-input', topic);
    const sendBtn = page.locator('#euler-send-btn, #voice-bar-send').first();
    if (await sendBtn.isVisible().catch(() => false)) {
      await sendBtn.click();
    } else {
      await page.locator('#euler-input').press('Enter');
    }

    // Wait for tutor to start speaking
    console.log('[Test] Waiting for tutor to start...');
    await waitForTutorStart(page);
    console.log('[Test] Tutor started');

    // Wait until we see an animation element appear in the DOM
    // (we don't need to wait for the whole lesson — just the first animation)
    console.log('[Test] Waiting for animation element to appear...');
    const animAppeared = await waitForAnimation(page, 60_000);
    if (!animAppeared) {
      result.issues.push('No animation element appeared in 60s');
      await captureArtifacts(page, topic, result);
      return result;
    }
    console.log('[Test] Animation element appeared');

    // Let the animation render for a few seconds
    console.log('[Test] Letting animation render (5s)...');
    await page.waitForTimeout(5000);

    // Inspect all animation canvases
    console.log('[Test] Inspecting animation canvases...');
    const inspection = await inspectAnimations(page);
    result.animationCount = inspection.total;
    result.renderedCount = inspection.rendered;

    console.log(`[Test] Found ${inspection.total} animations, ${inspection.rendered} rendered with content`);
    for (const a of inspection.details) {
      console.log(`       - ${a.type} @ ${a.width}x${a.height}: ${a.rendered ? 'RENDERED' : 'BLANK'} — ${a.reason}`);
    }

    // Collect issues
    if (inspection.total === 0) {
      result.issues.push('No animation canvas found in DOM');
    }
    if (inspection.rendered < inspection.total) {
      result.issues.push(`${inspection.total - inspection.rendered} of ${inspection.total} animations are blank`);
    }

    // Check console errors
    const animErrors = consoleMessages.filter(m =>
      m.type === 'error' && (
        m.text.includes('[Animation]') ||
        m.text.includes('[Board]') ||
        m.text.includes('THREE') ||
        m.text.includes('p5')
      )
    );
    const animWarnings = consoleMessages.filter(m =>
      m.type === 'warning' && (
        m.text.includes('BLACK') ||
        m.text.includes('TRANSPARENT') ||
        m.text.includes('cannot auto-reveal') ||
        m.text.includes('No AnimHelper')
      )
    );
    result.errorCount = animErrors.length + pageErrors.length;

    if (animErrors.length > 0) {
      result.issues.push(`${animErrors.length} animation errors in console`);
      for (const e of animErrors.slice(0, 3)) console.log(`  ERR: ${e.text.slice(0, 150)}`);
    }
    if (animWarnings.length > 0) {
      result.issues.push(`${animWarnings.length} animation warnings in console`);
      for (const w of animWarnings.slice(0, 3)) console.log(`  WARN: ${w.text.slice(0, 150)}`);
    }

    result.consoleSample = consoleMessages
      .filter(m => m.text.includes('[Animation]') || m.text.includes('[Figure]'))
      .slice(-20)
      .map(m => `[${m.type}] ${m.text}`);

    // Final verdict
    result.pass = inspection.total > 0 && inspection.rendered === inspection.total && result.errorCount === 0;

    await captureArtifacts(page, topic, result);
  } catch (error) {
    console.error('[Test] Error:', error.message);
    result.issues.push(`Test harness error: ${error.message}`);
    try { await captureArtifacts(page, topic, result); } catch {}
  } finally {
    await browser.close();
  }

  return result;
}

async function waitForTutorStart(page) {
  const start = Date.now();
  while (Date.now() - start < 30_000) {
    const started = await page.evaluate(() => {
      const status = document.querySelector('#vb-status, .vb-status');
      if (status) {
        const t = status.textContent.toLowerCase();
        if (t.includes('speaking') || t.includes('drawing') || t.includes('thinking')) return true;
      }
      // Also check if a scene has appeared
      return !!document.querySelector('.bd-scene .bd-el, .bd-scene .bd-text');
    }).catch(() => false);
    if (started) return true;
    await page.waitForTimeout(500);
  }
  return false;
}

async function waitForAnimation(page, timeoutMs) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const found = await page.evaluate(() => {
      // Any animation container — p5 (canvas) or Three.js (bd-scene3d)
      return !!document.querySelector('.bd-anim-figure canvas, .bd-scene3d canvas, .bd-anim-box canvas');
    }).catch(() => false);
    if (found) return true;
    await page.waitForTimeout(500);
  }
  return false;
}

async function inspectAnimations(page) {
  return await page.evaluate(() => {
    const result = { total: 0, rendered: 0, details: [] };

    // Find all animation canvases (both p5 and Three.js)
    const p5Canvases = document.querySelectorAll('.bd-anim-figure canvas, .bd-anim-box canvas');
    const threeCanvases = document.querySelectorAll('.bd-scene3d canvas');
    const canvases = [...p5Canvases, ...threeCanvases];

    for (const cvs of canvases) {
      result.total++;
      const detail = {
        type: cvs.closest('.bd-scene3d') ? 'three' : 'p5',
        width: cvs.width,
        height: cvs.height,
        rendered: false,
        reason: '',
      };

      if (cvs.width === 0 || cvs.height === 0) {
        detail.reason = 'canvas has zero size';
        result.details.push(detail);
        continue;
      }

      // For Three.js canvases (WebGL), we can't easily sample pixels.
      // Instead, check if the scene has children and if the renderer has rendered.
      if (detail.type === 'three') {
        // Look for BoardEngine to get the three scene entry
        let threeOk = false;
        let threeReason = 'unknown';
        try {
          if (window.BoardEngine && window.BoardEngine.state) {
            const anim = window.BoardEngine.state.animations.find(a =>
              a._threeScene && a.container && a.container.contains(cvs)
            );
            if (anim && anim._threeScene) {
              const nonLightChildren = anim._threeScene.children.filter(c =>
                c.type !== 'AmbientLight' &&
                c.type !== 'DirectionalLight' &&
                c.type !== 'AxesHelper' &&
                c.type !== 'GridHelper'
              );
              threeOk = nonLightChildren.length > 0;
              threeReason = `scene has ${nonLightChildren.length} non-light children`;
            } else {
              threeReason = 'no matching anim entry';
            }
          } else {
            threeReason = 'BoardEngine not exposed';
            // Fallback: assume rendered if the canvas has a WebGL context
            try {
              const gl = cvs.getContext('webgl', { preserveDrawingBuffer: true }) || cvs.getContext('webgl2', { preserveDrawingBuffer: true });
              if (gl) { threeOk = true; threeReason = 'has WebGL context (cannot verify pixels)'; }
            } catch {}
          }
        } catch (e) {
          threeReason = 'inspection error: ' + e.message;
        }
        detail.rendered = threeOk;
        detail.reason = threeReason;
        if (threeOk) result.rendered++;
        result.details.push(detail);
        continue;
      }

      // p5 canvas — sample several pixels across the canvas.
      // "Rendered" means: at least 5% of sampled pixels are non-background
      // (i.e., the LLM's drawing produced visible content beyond the bg fill).
      try {
        const ctx = cvs.getContext('2d', { willReadFrequently: true });
        if (!ctx) {
          detail.reason = 'no 2d context';
          result.details.push(detail);
          continue;
        }
        // Sample a 10x10 grid of pixels
        const samples = [];
        for (let x = 1; x <= 10; x++) {
          for (let y = 1; y <= 10; y++) {
            const px = ctx.getImageData(
              Math.floor((cvs.width * x) / 11),
              Math.floor((cvs.height * y) / 11),
              1, 1
            ).data;
            samples.push([px[0], px[1], px[2], px[3]]);
          }
        }

        // Board bg is #060e11 = rgb(6, 14, 17). "Rendered" pixels differ
        // from this by more than a small tolerance OR are transparent
        // (alpha < 250 means something was drawn on a transparent canvas).
        const boardBg = [6, 14, 17];
        const renderedPixels = samples.filter(([r, g, b, a]) => {
          if (a < 250) return false; // transparent = nothing drawn
          const dr = Math.abs(r - boardBg[0]);
          const dg = Math.abs(g - boardBg[1]);
          const db = Math.abs(b - boardBg[2]);
          return (dr + dg + db) > 20; // meaningfully different from bg
        });

        const allTransparent = samples.every(([, , , a]) => a < 10);
        const allBlack = samples.every(([r, g, b]) => r === 0 && g === 0 && b === 0);
        const renderedPct = (renderedPixels.length / samples.length) * 100;

        if (allTransparent) {
          detail.reason = 'canvas fully transparent — A.clear() override likely';
        } else if (allBlack) {
          detail.reason = 'canvas fully black — drawing failed';
        } else if (renderedPct < 5) {
          detail.reason = `only ${renderedPct.toFixed(0)}% of samples differ from bg — may be blank or only background`;
        } else {
          detail.rendered = true;
          detail.reason = `${renderedPct.toFixed(0)}% of samples have content`;
          result.rendered++;
        }
        result.details.push(detail);
      } catch (e) {
        detail.reason = 'sampling error: ' + e.message;
        result.details.push(detail);
      }
    }

    return result;
  });
}

async function captureArtifacts(page, topic, result) {
  const safe = topic.replace(/[^a-z0-9]+/gi, '_').slice(0, 40);
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const base = `${CONFIG.outputDir}/anim-${safe}-${stamp}`;
  try {
    await page.screenshot({ path: `${base}.png`, fullPage: true });
    console.log(`[Test] Screenshot: ${base}.png`);
  } catch (e) {
    console.warn('[Test] Screenshot failed:', e.message);
  }
  try {
    writeFileSync(`${base}-result.json`, JSON.stringify(result, null, 2));
    console.log(`[Test] Result JSON: ${base}-result.json`);
  } catch {}
}

main().catch(err => {
  console.error('FATAL:', err);
  process.exit(1);
});
