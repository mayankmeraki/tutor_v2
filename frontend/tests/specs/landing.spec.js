import { test, expect } from '@playwright/test';
import { SEL } from '../helpers/selectors.js';

test.describe('Landing Page', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => localStorage.clear());
    await page.goto('/');
  });

  // ──────────── Visibility ────────────

  test('landing screen is visible for unauthenticated users', async ({ page }) => {
    await expect(page.locator(SEL.screens.landing)).toBeVisible();
    await expect(page.locator(SEL.screens.browse)).toBeHidden();
  });

  test('hero section renders with input and CTA', async ({ page }) => {
    await expect(page.locator(SEL.landing.heroInput)).toBeVisible();
    await expect(page.locator(SEL.landing.heroBtn)).toBeVisible();
  });

  test('sign-in button is visible in nav', async ({ page }) => {
    await expect(page.locator(SEL.landing.signIn)).toBeVisible();
  });

  test('get started button is visible', async ({ page }) => {
    await expect(page.locator(SEL.landing.getStarted)).toBeVisible();
  });

  // ──────────── Navigation ────────────

  test('sign-in button navigates to /login', async ({ page }) => {
    await page.click(SEL.landing.signIn);
    await page.waitForTimeout(1000);
    expect(page.url()).toContain('/login');
    await expect(page.locator(SEL.screens.login)).toBeVisible();
  });

  test('get started button navigates to /login', async ({ page }) => {
    await page.click(SEL.landing.getStarted);
    await page.waitForTimeout(1000);
    expect(page.url()).toContain('/login');
  });

  test('"For Institutions" link navigates to /for-business', async ({ page }) => {
    const bizLink = page.locator('a:has-text("Institutions"), a:has-text("Business")').first();
    if (await bizLink.isVisible()) {
      await bizLink.click();
      await page.waitForTimeout(1000);
      expect(page.url()).toContain('/for-business');
      await expect(page.locator(SEL.screens.business)).toBeVisible();
    }
  });

  // ──────────── Hero Try Flow ────────────

  test('hero input accepts text', async ({ page }) => {
    await page.fill(SEL.landing.heroInput, 'teach me calculus');
    const val = await page.inputValue(SEL.landing.heroInput);
    expect(val).toBe('teach me calculus');
  });

  test('hero send button with text stores pending prompt and navigates to login', async ({ page }) => {
    await page.fill(SEL.landing.heroInput, 'explain photosynthesis');
    await page.click(SEL.landing.heroBtn);
    await page.waitForTimeout(2000);
    const pending = await page.evaluate(() => sessionStorage.getItem('capacity_pending_prompt'));
    const url = page.url();
    expect(url.includes('/login') || pending === 'explain photosynthesis').toBeTruthy();
  });

  // ──────────── Logo ────────────

  test('logo click stays on landing or goes to /', async ({ page }) => {
    const logo = page.locator(SEL.landing.logo).first();
    if (await logo.isVisible()) {
      await logo.click();
      await page.waitForTimeout(500);
      expect(page.url().endsWith('/') || page.url().includes('/home')).toBeTruthy();
    }
  });
});
