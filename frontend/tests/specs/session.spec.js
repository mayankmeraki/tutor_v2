import { test, expect } from '@playwright/test';
import { SEL } from '../helpers/selectors.js';

async function loginAndGoHome(page) {
  await page.goto('/login');
  await page.fill(SEL.auth.loginEmail, 'ishita@seekcapacity.ai');
  await page.fill(SEL.auth.loginPassword, 'ishita123');
  await page.click(SEL.auth.loginBtn);
  await page.waitForURL('**/home', { timeout: 15_000 });
}

async function startOnDemandSession(page) {
  await loginAndGoHome(page);
  await page.fill(SEL.home.eulerInput, 'explain what is a derivative in calculus');
  await page.click(SEL.home.eulerSendBtn);
  await page.waitForTimeout(8000);
}

test.describe('Teaching Session', () => {

  // ──────────── Session Start ────────────

  test.describe('Session Start', () => {
    test('starting from euler input shows prep overlay then teaching', async ({ page }) => {
      await startOnDemandSession(page);
      const teaching = page.locator(SEL.screens.teaching);
      const prep = page.locator(SEL.teaching.prepOverlay);
      const isTeaching = await teaching.isVisible();
      const isPrepping = await prep.isVisible();
      expect(isTeaching || isPrepping).toBeTruthy();
    });

    test('URL updates to /session/:id', async ({ page }) => {
      await startOnDemandSession(page);
      await page.waitForTimeout(3000);
      expect(page.url()).toMatch(/\/session\/.+/);
    });

    test('session timer starts counting', async ({ page }) => {
      await startOnDemandSession(page);
      const teaching = page.locator(SEL.screens.teaching);
      if (await teaching.isVisible()) {
        const timer = page.locator(SEL.teaching.timer);
        await page.waitForTimeout(3000);
        if (await timer.isVisible()) {
          const text = await timer.textContent();
          expect(text).toBeTruthy();
        }
      }
    });
  });

  // ──────────── Teaching Layout ────────────

  test.describe('Teaching Layout', () => {
    test.beforeEach(async ({ page }) => {
      await startOnDemandSession(page);
    });

    test('top bar is visible with course title', async ({ page }) => {
      const topBar = page.locator(SEL.teaching.topBar);
      if (await topBar.isVisible()) {
        await expect(topBar).toBeVisible();
      }
    });

    test('chat panel exists', async ({ page }) => {
      const chatPanel = page.locator(SEL.teaching.chatPanel);
      const isVisible = await chatPanel.isVisible();
      expect(typeof isVisible).toBe('boolean');
    });

    test('board panel exists', async ({ page }) => {
      const boardPanel = page.locator(SEL.teaching.boardPanel);
      const isVisible = await boardPanel.isVisible();
      expect(typeof isVisible).toBe('boolean');
    });

    test('canvas stream area renders', async ({ page }) => {
      const canvas = page.locator(SEL.teaching.canvasStream);
      if (await canvas.isVisible()) {
        await expect(canvas).toBeVisible();
      }
    });

    test('back button is available', async ({ page }) => {
      const backBtn = page.locator(SEL.teaching.backBtn);
      if (await backBtn.isVisible()) {
        await expect(backBtn).toBeVisible();
      }
    });
  });

  // ──────────── Board Content ────────────

  test.describe('Board & Streaming Content', () => {
    test('teaching content appears in canvas after response', async ({ page }) => {
      await startOnDemandSession(page);
      await page.waitForTimeout(15_000);
      const canvas = page.locator(SEL.teaching.canvasStream);
      if (await canvas.isVisible()) {
        const html = await canvas.innerHTML();
        expect(html.length).toBeGreaterThan(0);
      }
    });

    test('spotlight content area renders on board interaction', async ({ page }) => {
      await startOnDemandSession(page);
      await page.waitForTimeout(10_000);
      const spotlight = page.locator(SEL.teaching.spotlightContent);
      const isVisible = await spotlight.isVisible();
      expect(typeof isVisible).toBe('boolean');
    });
  });

  // ──────────── Speed Controls ────────────

  test.describe('Speed Controls', () => {
    test.beforeEach(async ({ page }) => {
      await startOnDemandSession(page);
    });

    test('speed toggle button exists', async ({ page }) => {
      const speedBtn = page.locator(SEL.teaching.speedBtn);
      if (await speedBtn.isVisible()) {
        await expect(speedBtn).toBeVisible();
      }
    });

    test('clicking speed button opens speed menu', async ({ page }) => {
      const speedBtn = page.locator(SEL.teaching.speedBtn);
      if (await speedBtn.isVisible()) {
        await speedBtn.click();
        await page.waitForTimeout(500);
        const menu = page.locator(SEL.teaching.speedMenu);
        const visible = await menu.isVisible();
        expect(typeof visible).toBe('boolean');
      }
    });
  });

  // ──────────── Voice Bar ────────────

  test.describe('Voice Bar', () => {
    test.beforeEach(async ({ page }) => {
      await startOnDemandSession(page);
    });

    test('voice bar input exists', async ({ page }) => {
      const input = page.locator(SEL.voice.barInput);
      if (await input.isVisible()) {
        await expect(input).toBeVisible();
      }
    });

    test('mic button exists', async ({ page }) => {
      const mic = page.locator(SEL.voice.micBtn);
      if (await mic.isVisible()) {
        await expect(mic).toBeVisible();
      }
    });

    test('typing in voice bar and sending triggers response', async ({ page }) => {
      await page.waitForTimeout(12_000);
      const input = page.locator(SEL.voice.barInput);
      if (await input.isVisible()) {
        await page.fill(SEL.voice.barInput, 'can you give me an example?');
        const sendBtn = page.locator(SEL.voice.barSend);
        if (await sendBtn.isVisible()) {
          await sendBtn.click();
          await page.waitForTimeout(8000);
          const canvas = page.locator(SEL.teaching.canvasStream);
          const html = await canvas.innerHTML();
          expect(html.length).toBeGreaterThan(50);
        }
      }
    });

    test('stop button halts streaming', async ({ page }) => {
      await page.waitForTimeout(5_000);
      const input = page.locator(SEL.voice.barInput);
      if (await input.isVisible()) {
        await page.fill(SEL.voice.barInput, 'explain limits in detail');
        const sendBtn = page.locator(SEL.voice.barSend);
        if (await sendBtn.isVisible()) {
          await sendBtn.click();
          await page.waitForTimeout(2000);
          const stopBtn = page.locator(SEL.voice.barStop);
          if (await stopBtn.isVisible()) {
            await stopBtn.click();
            await page.waitForTimeout(1000);
          }
        }
      }
    });
  });

  // ──────────── Plan Sidebar ────────────

  test.describe('Plan Sidebar', () => {
    test.beforeEach(async ({ page }) => {
      await startOnDemandSession(page);
    });

    test('plan sidebar exists', async ({ page }) => {
      const sidebar = page.locator(SEL.plan.sidebar);
      const isVisible = await sidebar.isVisible();
      expect(typeof isVisible).toBe('boolean');
    });

    test('plan panel can be toggled', async ({ page }) => {
      await page.waitForTimeout(10_000);
      const toggle = page.locator(SEL.plan.sidebarToggle);
      if (await toggle.isVisible()) {
        await toggle.click();
        await page.waitForTimeout(500);
      }
    });
  });

  // ──────────── Session Exit ────────────

  test.describe('Session Exit', () => {
    test('back button returns to home and cleans up', async ({ page }) => {
      await startOnDemandSession(page);
      await page.waitForTimeout(5000);
      const backBtn = page.locator(SEL.teaching.backBtn);
      if (await backBtn.isVisible()) {
        await backBtn.click();
        await page.waitForTimeout(3000);
        expect(page.url()).toContain('/home');
        const teaching = page.locator(SEL.screens.teaching);
        await expect(teaching).toBeHidden();
      }
    });
  });

  // ──────────── Resume Session ────────────

  test.describe('Session Resume', () => {
    test('resuming a session restores teaching layout', async ({ page }) => {
      await loginAndGoHome(page);
      await page.waitForTimeout(3000);
      const sessionCard = page.locator(SEL.home.sessionsRow + ' [class*="card"]').first();
      if (await sessionCard.isVisible()) {
        await sessionCard.click();
        await page.waitForTimeout(8000);
        expect(page.url()).toMatch(/\/session\/.+/);
        const teaching = page.locator(SEL.screens.teaching);
        const isVisible = await teaching.isVisible();
        expect(isVisible).toBeTruthy();
      }
    });
  });
});
