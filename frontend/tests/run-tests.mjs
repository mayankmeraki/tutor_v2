#!/usr/bin/env node
/**
 * Headless browser test runner using Puppeteer.
 * Runs interruption-test.html and reports results.
 */
import puppeteer from 'puppeteer';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const testFile = path.join(__dirname, 'interruption-test.html');

async function run() {
  const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox'] });
  const page = await browser.newPage();

  // Capture console output
  const logs = [];
  page.on('console', msg => {
    const text = msg.text();
    logs.push(text);
  });

  await page.goto(`file://${testFile}`, { waitUntil: 'networkidle0', timeout: 10000 });

  // Wait for tests to complete (summary element gets populated)
  await page.waitForFunction(() => {
    const s = document.getElementById('summary');
    return s && s.textContent.length > 0;
  }, { timeout: 10000 });

  // Get results
  const summary = await page.$eval('#summary', el => el.textContent);
  const allPass = await page.$eval('#summary', el => el.className.includes('allpass'));
  const testResults = await page.$$eval('.test', tests =>
    tests.map(t => ({
      name: t.querySelector('.test-name').textContent,
      status: t.classList.contains('pass') ? 'PASS' : 'FAIL',
      detail: t.querySelector('.test-detail').textContent,
    }))
  );

  await browser.close();

  // Report
  console.log('\n═══ Interruption System Tests ═══\n');
  for (const t of testResults) {
    const icon = t.status === 'PASS' ? '✓' : '✗';
    const color = t.status === 'PASS' ? '\x1b[32m' : '\x1b[31m';
    console.log(`${color}  ${icon} ${t.name}\x1b[0m${t.status === 'FAIL' ? `\n    ${t.detail}` : ''}`);
  }
  console.log(`\n${allPass ? '\x1b[32m' : '\x1b[31m'}${summary}\x1b[0m\n`);

  process.exit(allPass ? 0 : 1);
}

run().catch(e => { console.error('Test runner error:', e); process.exit(1); });
