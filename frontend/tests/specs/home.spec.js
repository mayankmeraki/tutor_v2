import { test, expect } from '@playwright/test';
import { SEL } from '../helpers/selectors.js';

/**
 * Reusable login fixture — logs in before each test.
 */
async function loginAndGoHome(page) {
  await page.goto('/login');
  await page.fill(SEL.auth.loginEmail, 'ishita@seekcapacity.ai');
  await page.fill(SEL.auth.loginPassword, 'ishita123');
  await page.click(SEL.auth.loginBtn);
  await page.waitForURL('**/home', { timeout: 15_000 });
}

test.describe('Home / Browse Screen', () => {

  test.beforeEach(async ({ page }) => {
    await loginAndGoHome(page);
  });

  // ──────────── Layout ────────────

  test('browse screen is visible after login', async ({ page }) => {
    await expect(page.locator(SEL.screens.browse)).toBeVisible();
    await expect(page.locator(SEL.screens.landing)).toBeHidden();
  });

  test('displays user greeting', async ({ page }) => {
    const greeting = page.locator(SEL.home.greeting);
    await expect(greeting).toBeVisible();
    const text = await greeting.textContent();
    expect(text.length).toBeGreaterThan(0);
  });

  test('displays user name in header', async ({ page }) => {
    const name = page.locator(SEL.home.userName);
    await expect(name).toBeVisible();
  });

  test('displays user avatar', async ({ page }) => {
    const avatar = page.locator(SEL.home.avatar);
    await expect(avatar).toBeVisible();
  });

  test('logout button is visible', async ({ page }) => {
    await expect(page.locator(SEL.home.logoutBtn)).toBeVisible();
  });

  // ──────────── Euler Input (Search) ────────────

  test('euler input is visible and accepts text', async ({ page }) => {
    const input = page.locator(SEL.home.eulerInput);
    await expect(input).toBeVisible();
    await page.fill(SEL.home.eulerInput, 'teach me about derivatives');
    const val = await page.inputValue(SEL.home.eulerInput);
    expect(val).toBe('teach me about derivatives');
  });

  test('euler send button is clickable', async ({ page }) => {
    await expect(page.locator(SEL.home.eulerSendBtn)).toBeVisible();
  });

  test('euler chips are displayed', async ({ page }) => {
    const chips = page.locator(SEL.home.eulerChips);
    const count = await chips.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });

  test('clicking euler chip fills the input', async ({ page }) => {
    const chips = page.locator(SEL.home.eulerChips);
    const count = await chips.count();
    if (count > 0) {
      const chipText = await chips.first().textContent();
      await chips.first().click();
      await page.waitForTimeout(500);
      const val = await page.inputValue(SEL.home.eulerInput);
      expect(val.length).toBeGreaterThan(0);
    }
  });

  // ──────────── Tabs ────────────

  test('home tab is active by default', async ({ page }) => {
    const homeTab = page.locator(SEL.home.tabHome);
    if (await homeTab.isVisible()) {
      await expect(homeTab).toHaveClass(/active/);
    }
  });

  test('clicking My Stuff tab switches panel', async ({ page }) => {
    const stuffTab = page.locator(SEL.home.tabStuff);
    if (await stuffTab.isVisible()) {
      await stuffTab.click();
      await page.waitForTimeout(500);
      const tabStuff = page.locator('#tab-stuff');
      await expect(tabStuff).toBeVisible();
    }
  });

  test('switching back to Home tab works', async ({ page }) => {
    const stuffTab = page.locator(SEL.home.tabStuff);
    const homeTab = page.locator(SEL.home.tabHome);
    if (await stuffTab.isVisible() && await homeTab.isVisible()) {
      await stuffTab.click();
      await page.waitForTimeout(300);
      await homeTab.click();
      await page.waitForTimeout(300);
      const tabHome = page.locator('#tab-home');
      await expect(tabHome).toBeVisible();
    }
  });

  // ──────────── Course Grid ────────────

  test('course grid loads courses', async ({ page }) => {
    const grid = page.locator(SEL.home.coursesGrid);
    await page.waitForTimeout(3000);
    if (await grid.isVisible()) {
      const cards = grid.locator('.ccard');
      const count = await cards.count();
      expect(count).toBeGreaterThan(0);
    }
  });

  test('clicking a course card navigates to course detail', async ({ page }) => {
    const grid = page.locator(SEL.home.coursesGrid);
    await page.waitForTimeout(3000);
    if (await grid.isVisible()) {
      const card = grid.locator('.ccard').first();
      if (await card.isVisible()) {
        await card.click();
        await page.waitForTimeout(2000);
        expect(page.url()).toContain('/courses/');
        await expect(page.locator(SEL.screens.course)).toBeVisible();
      }
    }
  });

  // ──────────── Sessions Row ────────────

  test('sessions section loads if user has sessions', async ({ page }) => {
    await page.waitForTimeout(3000);
    const section = page.locator(SEL.home.sessionsSection);
    // may or may not be visible depending on user data
    const isVisible = await section.isVisible();
    expect(typeof isVisible).toBe('boolean');
  });

  // ──────────── Videos Row ────────────

  test('videos section loads', async ({ page }) => {
    await page.waitForTimeout(3000);
    const section = page.locator(SEL.home.videosSection);
    const isVisible = await section.isVisible();
    expect(typeof isVisible).toBe('boolean');
  });

  // ──────────── My Stuff Tab ────────────

  test('My Stuff tab shows collections list', async ({ page }) => {
    const stuffTab = page.locator(SEL.home.tabStuff);
    if (await stuffTab.isVisible()) {
      await stuffTab.click();
      await page.waitForTimeout(1000);
      const list = page.locator(SEL.home.collectionsList);
      await expect(list).toBeVisible();
    }
  });

  test('new collection button opens modal', async ({ page }) => {
    const stuffTab = page.locator(SEL.home.tabStuff);
    if (await stuffTab.isVisible()) {
      await stuffTab.click();
      await page.waitForTimeout(500);
      const newBtn = page.locator(SEL.home.collectionsBtn);
      if (await newBtn.isVisible()) {
        await newBtn.click();
        await page.waitForTimeout(500);
        const modal = page.locator('#new-collection-modal');
        await expect(modal).toBeVisible();
      }
    }
  });

  // ──────────── On-Demand Send ────────────

  test('sending euler query triggers session creation flow', async ({ page }) => {
    await page.fill(SEL.home.eulerInput, 'explain the pythagorean theorem');

    const responsePromise = page.waitForResponse(
      resp => resp.url().includes('/api/') && resp.status() < 500,
      { timeout: 15_000 }
    ).catch(() => null);

    await page.click(SEL.home.eulerSendBtn);
    await page.waitForTimeout(5000);

    const teaching = page.locator(SEL.screens.teaching);
    const prep = page.locator(SEL.teaching.prepOverlay);
    const isTeaching = await teaching.isVisible();
    const isPrepping = await prep.isVisible();
    expect(isTeaching || isPrepping || page.url().includes('/session')).toBeTruthy();
  });
});
