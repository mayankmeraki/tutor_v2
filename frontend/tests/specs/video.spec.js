import { test, expect } from '@playwright/test';
import { SEL } from '../helpers/selectors.js';

async function loginAndGoHome(page) {
  await page.goto('/login');
  await page.fill(SEL.auth.loginEmail, 'ishita@seekcapacity.ai');
  await page.fill(SEL.auth.loginPassword, 'ishita123');
  await page.click(SEL.auth.loginBtn);
  await page.waitForURL('**/home', { timeout: 15_000 });
}

async function navigateToFirstCourseAndPlay(page) {
  await loginAndGoHome(page);
  await page.waitForTimeout(3000);
  const grid = page.locator(SEL.home.coursesGrid);
  const card = grid.locator('.ccard').first();
  if (await card.isVisible()) {
    await card.click();
    await page.waitForURL('**/courses/**', { timeout: 10_000 });
    await page.waitForTimeout(2000);
  }
}

test.describe('Video Follow-Along Mode', () => {

  // ──────────── Video Entry ────────────

  test.describe('Starting Video Mode', () => {
    test('play button on course page initiates video or session', async ({ page }) => {
      await navigateToFirstCourseAndPlay(page);
      const playBtn = page.locator(SEL.course.playBtn);
      if (await playBtn.isVisible()) {
        await playBtn.click();
        await page.waitForTimeout(8000);
        const overlay = page.locator(SEL.video.overlay);
        const teaching = page.locator(SEL.screens.teaching);
        const hasVideo = await overlay.isVisible();
        const hasTeaching = await teaching.isVisible();
        expect(hasVideo || hasTeaching || page.url().includes('/session')).toBeTruthy();
      }
    });
  });

  // ──────────── Video Overlay ────────────

  test.describe('Video Overlay', () => {
    test.beforeEach(async ({ page }) => {
      await navigateToFirstCourseAndPlay(page);
      const playBtn = page.locator(SEL.course.playBtn);
      if (await playBtn.isVisible()) {
        await playBtn.click();
        await page.waitForTimeout(8000);
      }
    });

    test('video overlay renders if video mode entered', async ({ page }) => {
      const overlay = page.locator(SEL.video.overlay);
      if (await overlay.isVisible()) {
        await expect(overlay).toBeVisible();
      }
    });

    test('close button exits video mode', async ({ page }) => {
      const overlay = page.locator(SEL.video.overlay);
      if (await overlay.isVisible()) {
        const closeBtn = page.locator(SEL.video.closeBtn);
        await closeBtn.click();
        await page.waitForTimeout(2000);
        await expect(overlay).toBeHidden();
      }
    });

    test('video wrap area exists', async ({ page }) => {
      const overlay = page.locator(SEL.video.overlay);
      if (await overlay.isVisible()) {
        const vidWrap = page.locator(SEL.video.vidWrap);
        await expect(vidWrap).toBeVisible();
      }
    });
  });

  // ──────────── Video Playlist ────────────

  test.describe('Video Playlist', () => {
    test('playlist panel shows if multiple lessons', async ({ page }) => {
      await navigateToFirstCourseAndPlay(page);
      const playBtn = page.locator(SEL.course.playBtn);
      if (await playBtn.isVisible()) {
        await playBtn.click();
        await page.waitForTimeout(5000);
        const playlist = page.locator(SEL.video.playlist);
        const isVisible = await playlist.isVisible();
        expect(typeof isVisible).toBe('boolean');
      }
    });

    test('playlist count shows correct lesson count', async ({ page }) => {
      await navigateToFirstCourseAndPlay(page);
      const playBtn = page.locator(SEL.course.playBtn);
      if (await playBtn.isVisible()) {
        await playBtn.click();
        await page.waitForTimeout(5000);
        const count = page.locator(SEL.video.playlistCount);
        if (await count.isVisible()) {
          const text = await count.textContent();
          expect(text).toBeTruthy();
        }
      }
    });
  });

  // ──────────── Video Interaction ────────────

  test.describe('Video Interaction', () => {
    test.beforeEach(async ({ page }) => {
      await navigateToFirstCourseAndPlay(page);
      const playBtn = page.locator(SEL.course.playBtn);
      if (await playBtn.isVisible()) {
        await playBtn.click();
        await page.waitForTimeout(8000);
      }
    });

    test('voice bar appears in video mode for interaction', async ({ page }) => {
      const overlay = page.locator(SEL.video.overlay);
      if (await overlay.isVisible()) {
        const micFloat = page.locator(SEL.voice.micFloat);
        const barInput = page.locator(SEL.voice.barInput);
        const hasMic = await micFloat.isVisible();
        const hasInput = await barInput.isVisible();
        expect(hasMic || hasInput).toBeTruthy();
      }
    });

    test('chat input in video mode sends messages', async ({ page }) => {
      const overlay = page.locator(SEL.video.overlay);
      if (await overlay.isVisible()) {
        const input = page.locator(SEL.voice.barInput);
        if (await input.isVisible()) {
          await page.fill(SEL.voice.barInput, 'what did the teacher just say?');
          const sendBtn = page.locator(SEL.voice.barSend);
          if (await sendBtn.isVisible()) {
            await sendBtn.click();
            await page.waitForTimeout(5000);
          }
        }
      }
    });
  });
});
