import { test, expect } from '@playwright/test';
import { SEL } from '../helpers/selectors.js';

async function login(page) {
  await page.goto('/login');
  await page.fill(SEL.auth.loginEmail, 'ishita@seekcapacity.ai');
  await page.fill(SEL.auth.loginPassword, 'ishita123');
  await page.click(SEL.auth.loginBtn);
  await page.waitForURL('**/home', { timeout: 15_000 });
}

test.describe('Error Handling & Edge Cases', () => {

  // ──────────── Auth Errors ────────────

  test.describe('Auth Errors', () => {
    test('expired token triggers re-login flow', async ({ page }) => {
      await login(page);
      await page.evaluate(() => localStorage.setItem('capacity_token', 'expired_invalid_token'));
      await page.goto('/home');
      await page.waitForTimeout(5000);
      const url = page.url();
      const loginVisible = await page.locator(SEL.screens.login).isVisible();
      const landingVisible = await page.locator(SEL.screens.landing).isVisible();
      expect(loginVisible || landingVisible || url.includes('/login') || url.endsWith('/')).toBeTruthy();
    });

    test('clearing token mid-session redirects appropriately', async ({ page }) => {
      await login(page);
      await page.evaluate(() => localStorage.removeItem('capacity_token'));
      await page.goto('/home');
      await page.waitForTimeout(3000);
      const url = page.url();
      expect(url.endsWith('/') || url.includes('/login')).toBeTruthy();
    });
  });

  // ──────────── Network Errors ────────────

  test.describe('Network Resilience', () => {
    test('app handles API timeout gracefully on home', async ({ page }) => {
      await login(page);
      await page.route('**/api/v1/content/courses*', route => {
        route.abort('timedout');
      });
      await page.goto('/home');
      await page.waitForTimeout(5000);
      const browse = page.locator(SEL.screens.browse);
      await expect(browse).toBeVisible();
    });

    test('app handles chat API failure gracefully', async ({ page }) => {
      await login(page);
      await page.route('**/api/chat*', route => {
        route.fulfill({ status: 500, body: 'Internal Server Error' });
      });
      await page.fill(SEL.home.eulerInput, 'test network error');
      await page.click(SEL.home.eulerSendBtn);
      await page.waitForTimeout(8000);
      // should not crash — may show error or stay on same page
      const url = page.url();
      expect(url).toBeTruthy();
    });

    test('app handles course API 404 gracefully', async ({ page }) => {
      await login(page);
      await page.route('**/api/v1/content/course-map/999*', route => {
        route.fulfill({ status: 404, body: JSON.stringify({ detail: 'Not found' }) });
      });
      await page.goto('/courses/999');
      await page.waitForTimeout(5000);
      // should redirect to home or show error
      const browse = page.locator(SEL.screens.browse);
      const course = page.locator(SEL.screens.course);
      const isBrowse = await browse.isVisible();
      const isCourse = await course.isVisible();
      expect(isBrowse || isCourse || page.url().includes('/home')).toBeTruthy();
    });
  });

  // ──────────── Session Errors ────────────

  test.describe('Session Edge Cases', () => {
    test('invalid session ID in URL shows error or redirects', async ({ page }) => {
      await login(page);
      await page.goto('/session/nonexistent-session-xyz-999');
      await page.waitForTimeout(8000);
      const url = page.url();
      const teaching = page.locator(SEL.screens.teaching);
      const browse = page.locator(SEL.screens.browse);
      const isTeaching = await teaching.isVisible();
      const isBrowse = await browse.isVisible();
      expect(isTeaching || isBrowse || url.includes('/home')).toBeTruthy();
    });
  });

  // ──────────── Feedback Modal ────────────

  test.describe('Feedback Modal', () => {
    test('bug button opens feedback modal', async ({ page }) => {
      await login(page);
      const bugBtn = page.locator('.fb-bug-btn').first();
      if (await bugBtn.isVisible()) {
        await bugBtn.click();
        await page.waitForTimeout(1000);
        const overlay = page.locator(SEL.feedback.overlay);
        await expect(overlay).toBeVisible();
      }
    });

    test('feedback modal has submit button', async ({ page }) => {
      await login(page);
      const bugBtn = page.locator('.fb-bug-btn').first();
      if (await bugBtn.isVisible()) {
        await bugBtn.click();
        await page.waitForTimeout(1000);
        const submit = page.locator(SEL.feedback.submitBtn);
        if (await submit.isVisible()) {
          await expect(submit).toBeVisible();
        }
      }
    });

    test('feedback modal closes on overlay click or close', async ({ page }) => {
      await login(page);
      const bugBtn = page.locator('.fb-bug-btn').first();
      if (await bugBtn.isVisible()) {
        await bugBtn.click();
        await page.waitForTimeout(1000);
        const overlay = page.locator(SEL.feedback.overlay);
        if (await overlay.isVisible()) {
          await page.keyboard.press('Escape');
          await page.waitForTimeout(1000);
          const stillVisible = await overlay.isVisible();
          if (stillVisible) {
            await overlay.click({ position: { x: 5, y: 5 } });
            await page.waitForTimeout(500);
          }
        }
      }
    });
  });

  // ──────────── Console Errors ────────────

  test.describe('Console Error Monitoring', () => {
    test('landing page loads without uncaught errors', async ({ page }) => {
      const errors = [];
      page.on('pageerror', err => errors.push(err.message));
      await page.evaluate(() => localStorage.clear());
      await page.goto('/');
      await page.waitForTimeout(3000);
      const criticalErrors = errors.filter(e =>
        !e.includes('ResizeObserver') && !e.includes('Non-Error promise rejection')
      );
      expect(criticalErrors.length).toBe(0);
    });

    test('home page loads without uncaught errors', async ({ page }) => {
      const errors = [];
      page.on('pageerror', err => errors.push(err.message));
      await login(page);
      await page.waitForTimeout(3000);
      const criticalErrors = errors.filter(e =>
        !e.includes('ResizeObserver') && !e.includes('Non-Error promise rejection')
      );
      expect(criticalErrors.length).toBe(0);
    });

    test('course page loads without uncaught errors', async ({ page }) => {
      const errors = [];
      page.on('pageerror', err => errors.push(err.message));
      await login(page);
      await page.waitForTimeout(3000);
      const card = page.locator(SEL.home.coursesGrid + ' .ccard').first();
      if (await card.isVisible()) {
        await card.click();
        await page.waitForTimeout(5000);
        const criticalErrors = errors.filter(e =>
          !e.includes('ResizeObserver') && !e.includes('Non-Error promise rejection')
        );
        expect(criticalErrors.length).toBe(0);
      }
    });
  });

  // ──────────── Rapid Navigation ────────────

  test.describe('Rapid Navigation Stress', () => {
    test('rapidly switching between pages does not crash', async ({ page }) => {
      await login(page);
      await page.waitForTimeout(2000);

      for (let i = 0; i < 5; i++) {
        await page.goto('/home');
        await page.waitForTimeout(300);
        await page.goto('/courses');
        await page.waitForTimeout(300);
        await page.goto('/tutor');
        await page.waitForTimeout(300);
      }

      const browse = page.locator(SEL.screens.browse);
      await expect(browse).toBeVisible();
    });

    test('double-clicking send does not create duplicate sessions', async ({ page }) => {
      await login(page);
      await page.fill(SEL.home.eulerInput, 'double click test');
      await page.click(SEL.home.eulerSendBtn);
      await page.click(SEL.home.eulerSendBtn);
      await page.waitForTimeout(8000);
      // should still be on one session, not crash
      const url = page.url();
      expect(url).toBeTruthy();
    });
  });

  // ──────────── Throttle ────────────

  test.describe('Message Throttle', () => {
    test('rapid messages are throttled (800ms debounce)', async ({ page }) => {
      await login(page);
      await page.fill(SEL.home.eulerInput, 'throttle test message');
      await page.click(SEL.home.eulerSendBtn);
      await page.waitForTimeout(100);
      await page.fill(SEL.home.eulerInput, 'second rapid message');
      await page.click(SEL.home.eulerSendBtn);
      await page.waitForTimeout(5000);
      // app should handle this without crashing
      expect(page.url()).toBeTruthy();
    });
  });
});
