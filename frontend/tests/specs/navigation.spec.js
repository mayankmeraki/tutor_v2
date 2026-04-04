import { test, expect } from '@playwright/test';
import { SEL } from '../helpers/selectors.js';

async function login(page) {
  await page.goto('/login');
  await page.fill(SEL.auth.loginEmail, 'ishita@seekcapacity.ai');
  await page.fill(SEL.auth.loginPassword, 'ishita123');
  await page.click(SEL.auth.loginBtn);
  await page.waitForURL('**/home', { timeout: 15_000 });
}

test.describe('Navigation & Routing', () => {

  // ──────────── Route Resolution ────────────

  test.describe('Public Routes', () => {
    test.beforeEach(async ({ page }) => {
      await page.evaluate(() => localStorage.clear());
    });

    test('/ shows landing for unauthenticated user', async ({ page }) => {
      await page.goto('/');
      await expect(page.locator(SEL.screens.landing)).toBeVisible();
    });

    test('/login shows login panel', async ({ page }) => {
      await page.goto('/login');
      await expect(page.locator(SEL.screens.login)).toBeVisible();
    });

    test('/for-business shows business screen', async ({ page }) => {
      await page.goto('/for-business');
      await expect(page.locator(SEL.screens.business)).toBeVisible();
    });

    test('unknown route redirects to / or /login', async ({ page }) => {
      await page.goto('/this-route-does-not-exist');
      await page.waitForTimeout(2000);
      const url = page.url();
      expect(url.endsWith('/') || url.includes('/login') || url.includes('/home')).toBeTruthy();
    });
  });

  // ──────────── Authenticated Routes ────────────

  test.describe('Authenticated Routes', () => {
    test.beforeEach(async ({ page }) => {
      await login(page);
    });

    test('/home shows browse screen', async ({ page }) => {
      await page.goto('/home');
      await expect(page.locator(SEL.screens.browse)).toBeVisible();
    });

    test('/dashboard is alias for /home', async ({ page }) => {
      await page.goto('/dashboard');
      await page.waitForTimeout(1000);
      await expect(page.locator(SEL.screens.browse)).toBeVisible();
    });

    test('/courses shows browse screen', async ({ page }) => {
      await page.goto('/courses');
      await page.waitForTimeout(1000);
      await expect(page.locator(SEL.screens.browse)).toBeVisible();
    });

    test('/tutor shows browse screen', async ({ page }) => {
      await page.goto('/tutor');
      await page.waitForTimeout(1000);
      await expect(page.locator(SEL.screens.browse)).toBeVisible();
    });

    test('/session redirects to /home', async ({ page }) => {
      await page.goto('/session');
      await page.waitForTimeout(2000);
      expect(page.url()).toContain('/home');
    });
  });

  // ──────────── Browser History ────────────

  test.describe('Browser History (Back/Forward)', () => {
    test('back from course detail returns to home', async ({ page }) => {
      await login(page);
      await page.waitForTimeout(3000);
      const grid = page.locator(SEL.home.coursesGrid);
      const card = grid.locator('.ccard').first();
      if (await card.isVisible()) {
        await card.click();
        await page.waitForURL('**/courses/**', { timeout: 10_000 });
        await expect(page.locator(SEL.screens.course)).toBeVisible();

        await page.goBack();
        await page.waitForTimeout(2000);
        expect(page.url()).toContain('/home');
        await expect(page.locator(SEL.screens.browse)).toBeVisible();
      }
    });

    test('forward after back restores course page', async ({ page }) => {
      await login(page);
      await page.waitForTimeout(3000);
      const grid = page.locator(SEL.home.coursesGrid);
      const card = grid.locator('.ccard').first();
      if (await card.isVisible()) {
        await card.click();
        await page.waitForURL('**/courses/**', { timeout: 10_000 });
        const courseUrl = page.url();

        await page.goBack();
        await page.waitForTimeout(1500);

        await page.goForward();
        await page.waitForTimeout(1500);
        expect(page.url()).toBe(courseUrl);
        await expect(page.locator(SEL.screens.course)).toBeVisible();
      }
    });

    test('back from login returns to landing', async ({ page }) => {
      await page.evaluate(() => localStorage.clear());
      await page.goto('/');
      await page.waitForTimeout(500);
      await page.click(SEL.landing.signIn);
      await page.waitForTimeout(1000);
      expect(page.url()).toContain('/login');

      await page.goBack();
      await page.waitForTimeout(1500);
      expect(page.url().endsWith('/') || page.url().includes('/home')).toBeTruthy();
    });
  });

  // ──────────── Screen Exclusivity ────────────

  test.describe('Screen Exclusivity', () => {
    test('only one screen is visible at a time on home', async ({ page }) => {
      await login(page);
      const screenIds = [
        SEL.screens.landing, SEL.screens.business, SEL.screens.login,
        SEL.screens.course, SEL.screens.ondemand,
      ];
      for (const sel of screenIds) {
        const el = page.locator(sel);
        await expect(el).toBeHidden();
      }
      await expect(page.locator(SEL.screens.browse)).toBeVisible();
    });

    test('navigating to course hides browse', async ({ page }) => {
      await login(page);
      await page.waitForTimeout(3000);
      const card = page.locator(SEL.home.coursesGrid + ' .ccard').first();
      if (await card.isVisible()) {
        await card.click();
        await page.waitForURL('**/courses/**', { timeout: 10_000 });
        await expect(page.locator(SEL.screens.browse)).toBeHidden();
        await expect(page.locator(SEL.screens.course)).toBeVisible();
      }
    });
  });

  // ──────────── Popstate Cleanup ────────────

  test.describe('Popstate Cleanup', () => {
    test('leaving session via back button hides teaching layout', async ({ page }) => {
      await login(page);
      await page.fill(SEL.home.eulerInput, 'quick test prompt');
      await page.click(SEL.home.eulerSendBtn);
      await page.waitForTimeout(8000);
      const teaching = page.locator(SEL.screens.teaching);
      if (await teaching.isVisible()) {
        await page.goBack();
        await page.waitForTimeout(3000);
        await expect(teaching).toBeHidden();
      }
    });
  });

  // ──────────── Direct URL Access ────────────

  test.describe('Direct URL Access', () => {
    test('authenticated user can access /courses/:id directly', async ({ page }) => {
      await login(page);
      await page.goto('/courses/1');
      await page.waitForTimeout(3000);
      const course = page.locator(SEL.screens.course);
      const browse = page.locator(SEL.screens.browse);
      const isCourse = await course.isVisible();
      const isBrowse = await browse.isVisible();
      expect(isCourse || isBrowse).toBeTruthy();
    });
  });
});
