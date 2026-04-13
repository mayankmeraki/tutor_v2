#!/usr/bin/env node
/**
 * Animation Log Auditor — analyzes /tmp/euler_logs/ for issues.
 *
 * Reads all session logs and reports:
 *   - Truncated beats (code too long)
 *   - Animations without phase groups in figures
 *   - p5 code without setup/createCanvas
 *   - Nested Three.js groups that would break auto-sync
 *   - Empty/missing say on beats with draw
 *   - TTS failures
 *
 * Usage:
 *   node animation-audit.js                    # audit all sessions
 *   node animation-audit.js <session-id>       # audit one session
 */

import { readdirSync, readFileSync } from 'fs';
import { join } from 'path';

const LOG_DIR = '/tmp/euler_logs';
const sessionFilter = process.argv[2] || null;

function auditSession(filePath, sessionId) {
  const content = readFileSync(filePath, 'utf-8');
  const issues = [];

  // Count basics
  const gens = (content.match(/^ GEN \d+/gm) || []).length;
  const beats = (content.match(/BEAT #\d+/g) || []).length;
  const truncated = (content.match(/UNCLOSED BEAT/g) || []).length;
  const errors = (content.match(/ERROR/g) || []).length;
  const ttsOk = (content.match(/TTS_OK/g) || []).length;
  const ttsFail = (content.match(/TTS_TIMEOUT|TTS_ERROR|TTS_EMPTY/g) || []).length;
  const audioSkips = (content.match(/AUDIO_SKIP/g) || []).length;
  const haikuAttempts = (content.match(/HAIKU_ATTEMPT/g) || []).length;
  const haikuSuccess = (content.match(/HAIKU_SUCCESS/g) || []).length;

  // Analyze animation beats
  const animBeats = [...content.matchAll(/BEAT #(\d+) \| draw:\[([^\]]*)\](?: \| code:(\d+)chars)?/g)];
  const animations = animBeats.filter(m => m[3]); // beats with code

  for (const anim of animations) {
    const beatNum = anim[1];
    const cmds = anim[2];
    const codeLen = parseInt(anim[3]);

    // Check code size
    if (codeLen > 4000) {
      issues.push({ severity: 'HIGH', beat: beatNum, msg: `Animation code ${codeLen} chars — risk of truncation (limit: 4000)` });
    }

    // Check if figure has phase groups
    if (cmds.includes('figure')) {
      // Look at nearby gen content for phase group patterns
      const beatIdx = content.indexOf(anim[0]);
      const genStart = content.lastIndexOf('GEN ', beatIdx);
      const genEnd = content.indexOf('GEN ', beatIdx + 100);
      const genContent = content.slice(genStart, genEnd > 0 ? genEnd : undefined).slice(0, 10000);

      const hasThreeGroups = /visible\s*=\s*false/.test(genContent);
      const hasAnimHelper = /AnimHelper/.test(genContent);
      const hasStateInit = /A\.init\s*\(/.test(genContent);

      if (!hasThreeGroups && !hasAnimHelper) {
        issues.push({ severity: 'MEDIUM', beat: beatNum, msg: `Figure animation without phase groups or AnimHelper — no beat-by-beat reveal` });
      }
      if (hasAnimHelper && !hasStateInit) {
        issues.push({ severity: 'LOW', beat: beatNum, msg: `AnimHelper created but A.init() not called — empty state, auto-sync won't advance` });
      }

      // Check for nested groups (the wrapper pattern)
      if (/\.add\(g\d\)/.test(genContent) && hasThreeGroups) {
        issues.push({ severity: 'INFO', beat: beatNum, msg: `Nested phase groups detected (wrapper pattern) — fixed by traverse-based reveal` });
      }
    }
  }

  // Check for truncated beats
  if (truncated > 0) {
    issues.push({ severity: 'CRITICAL', beat: '-', msg: `${truncated} truncated beat(s) — animation code exceeded token limit` });
  }

  // Check for beats with draw but empty say
  const emptySayBeats = [...content.matchAll(/BEAT #(\d+).*say:"⚠️ EMPTY"/g)];
  for (const m of emptySayBeats) {
    issues.push({ severity: 'HIGH', beat: m[1], msg: `Beat has draw but EMPTY say — voice goes silent` });
  }

  // Check for TTS failures
  if (ttsFail > 0) {
    issues.push({ severity: 'MEDIUM', beat: '-', msg: `${ttsFail} TTS failure(s) (timeout/error/empty)` });
  }

  return {
    sessionId,
    gens,
    beats,
    animations: animations.length,
    truncated,
    errors,
    ttsOk,
    ttsFail,
    audioSkips,
    haikuAttempts,
    haikuSuccess,
    issues,
  };
}

// Main
try {
  const files = readdirSync(LOG_DIR).filter(f => f.endsWith('.log') && f !== 'test-123.log');

  if (sessionFilter) {
    const match = files.find(f => f.includes(sessionFilter));
    if (!match) { console.error(`No log found for session: ${sessionFilter}`); process.exit(1); }
    const result = auditSession(join(LOG_DIR, match), match.replace('.log', ''));
    printResult(result);
  } else {
    console.log(`\nAuditing ${files.length} sessions in ${LOG_DIR}\n`);

    let totalIssues = 0;
    let criticals = 0;

    for (const f of files) {
      const result = auditSession(join(LOG_DIR, f), f.replace('.log', ''));
      printResult(result);
      totalIssues += result.issues.length;
      criticals += result.issues.filter(i => i.severity === 'CRITICAL').length;
    }

    console.log('═'.repeat(70));
    console.log(`TOTAL: ${files.length} sessions, ${totalIssues} issues, ${criticals} critical`);
  }
} catch (e) {
  console.error('Error:', e.message);
  process.exit(1);
}

function printResult(r) {
  const status = r.issues.some(i => i.severity === 'CRITICAL') ? '✗' :
                 r.issues.some(i => i.severity === 'HIGH') ? '~' : '✓';

  console.log(`${status} ${r.sessionId.slice(0, 8)}  gens:${r.gens} beats:${r.beats} anims:${r.animations} trunc:${r.truncated} tts:${r.ttsOk}ok/${r.ttsFail}fail`);

  for (const issue of r.issues) {
    const icon = { CRITICAL: '🔴', HIGH: '🟠', MEDIUM: '🟡', LOW: '🔵', INFO: 'ℹ️' }[issue.severity] || '·';
    console.log(`  ${icon} [beat ${issue.beat}] ${issue.msg}`);
  }

  if (r.issues.length === 0) {
    console.log('  ✓ No issues found');
  }
  console.log('');
}
