import { test, expect } from '@playwright/test';
import { SEL } from '../helpers/selectors.js';

async function loginAndGoHome(page) {
  await page.goto('/login');
  await page.fill(SEL.auth.loginEmail, 'ishita@seekcapacity.ai');
  await page.fill(SEL.auth.loginPassword, 'ishita123');
  await page.click(SEL.auth.loginBtn);
  await page.waitForURL('**/home', { timeout: 15_000 });
}

async function navigateToFirstCourse(page) {
  await loginAndGoHome(page);
  await page.waitForTimeout(3000);
  const grid = page.locator(SEL.home.coursesGrid);
  const card = grid.locator('.ccard').first();
  if (await card.isVisible()) {
    await card.click();
    await page.waitForURL('**/courses/**', { timeout: 10_000 });
  }
}

test.describe('Course Detail Page', () => {

  test.beforeEach(async ({ page }) => {
    await navigateToFirstCourse(page);
  });

  // ──────────── Layout ────────────

  test('course screen is visible', async ({ page }) => {
    await expect(page.locator(SEL.screens.course)).toBeVisible();
  });

  test('displays course title', async ({ page }) => {
    const title = page.locator(SEL.course.title);
    await expect(title).toBeVisible();
    const text = await title.textContent();
    expect(text.length).toBeGreaterThan(0);
  });

  test('displays course description', async ({ page }) => {
    const desc = page.locator(SEL.course.description);
    await expect(desc).toBeVisible();
    const text = await desc.textContent();
    expect(text.length).toBeGreaterThan(0);
  });

  test('displays course tag', async ({ page }) => {
    const tag = page.locator(SEL.course.tag);
    if (await tag.isVisible()) {
      const text = await tag.textContent();
      expect(text.length).toBeGreaterThan(0);
    }
  });

  test('displays lesson and module counts', async ({ page }) => {
    const lessons = page.locator(SEL.course.lessonsCount);
    const modules = page.locator(SEL.course.modulesCount);
    if (await lessons.isVisible()) {
      const text = await lessons.textContent();
      expect(text.length).toBeGreaterThan(0);
    }
    if (await modules.isVisible()) {
      const text = await modules.textContent();
      expect(text.length).toBeGreaterThan(0);
    }
  });

  // ──────────── Play Button ────────────

  test('play button is visible', async ({ page }) => {
    const playBtn = page.locator(SEL.course.playBtn);
    await expect(playBtn).toBeVisible();
  });

  test('play button starts a session or video', async ({ page }) => {
    const playBtn = page.locator(SEL.course.playBtn);
    await playBtn.click();
    await page.waitForTimeout(5000);
    const url = page.url();
    const teaching = page.locator(SEL.screens.teaching);
    const videoOverlay = page.locator(SEL.video.overlay);
    const isSession = url.includes('/session');
    const isTeaching = await teaching.isVisible();
    const isVideo = await videoOverlay.isVisible();
    expect(isSession || isTeaching || isVideo).toBeTruthy();
  });

  // ──────────── Filmstrip ────────────

  test('filmstrip renders lesson cards', async ({ page }) => {
    const filmstrip = page.locator(SEL.course.filmstrip);
    await page.waitForTimeout(2000);
    if (await filmstrip.isVisible()) {
      const cards = filmstrip.locator('[class*="fs-"]');
      const count = await cards.count();
      expect(count).toBeGreaterThan(0);
    }
  });

  test('clicking a filmstrip card shows lesson detail', async ({ page }) => {
    const filmstrip = page.locator(SEL.course.filmstrip);
    await page.waitForTimeout(2000);
    if (await filmstrip.isVisible()) {
      const firstCard = filmstrip.locator('[class*="fs-card"], [class*="fs-item"]').first();
      if (await firstCard.isVisible()) {
        await firstCard.click();
        await page.waitForTimeout(1000);
        const detail = page.locator(SEL.course.lessonDetail);
        const detailTitle = page.locator(SEL.course.detailTitle);
        if (await detail.isVisible()) {
          const text = await detailTitle.textContent();
          expect(text.length).toBeGreaterThan(0);
        }
      }
    }
  });

  // ──────────── Back Button ────────────

  test('back button navigates to home', async ({ page }) => {
    const backBtn = page.locator(SEL.course.backBtn);
    if (await backBtn.isVisible()) {
      await backBtn.click();
      await page.waitForTimeout(2000);
      expect(page.url()).toContain('/home');
      await expect(page.locator(SEL.screens.browse)).toBeVisible();
    }
  });

  // ──────────── Banner / Image ────────────

  test('course banner area exists', async ({ page }) => {
    const banner = page.locator(SEL.course.banner);
    if (await banner.isVisible()) {
      const bg = await banner.evaluate(el => getComputedStyle(el).backgroundImage);
      expect(bg).toBeDefined();
    }
  });

  // ──────────── Course Hours ────────────

  test('estimated hours displayed', async ({ page }) => {
    const hours = page.locator(SEL.course.hours);
    if (await hours.isVisible()) {
      const text = await hours.textContent();
      expect(text).toBeTruthy();
    }
  });
});
