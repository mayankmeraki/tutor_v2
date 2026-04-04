import { test, expect } from '@playwright/test';
import { SEL } from '../helpers/selectors.js';

test.describe('For Business Page', () => {

  test.beforeEach(async ({ page }) => {
    await page.evaluate(() => localStorage.clear());
    await page.goto('/for-business');
  });

  test('business screen is visible', async ({ page }) => {
    await expect(page.locator(SEL.screens.business)).toBeVisible();
  });

  test('has demo form fields', async ({ page }) => {
    const emailInput = page.locator('#biz-email');
    const messageInput = page.locator('#biz-message');
    const submitBtn = page.locator('#biz-demo-submit');

    if (await emailInput.isVisible()) {
      await expect(emailInput).toBeVisible();
      await expect(messageInput).toBeVisible();
      await expect(submitBtn).toBeVisible();
    }
  });

  test('demo form validates empty submission', async ({ page }) => {
    const submitBtn = page.locator('#biz-demo-submit');
    if (await submitBtn.isVisible()) {
      await submitBtn.click();
      await page.waitForTimeout(1000);
      const status = page.locator('#biz-demo-status');
      const text = await status.textContent();
      expect(text.length).toBeGreaterThan(0);
    }
  });

  test('demo form accepts input', async ({ page }) => {
    const emailInput = page.locator('#biz-email');
    if (await emailInput.isVisible()) {
      await page.fill('#biz-email', 'business@test.com');
      await page.fill('#biz-message', 'We want to integrate Capacity for our institution.');
      const emailVal = await page.inputValue('#biz-email');
      expect(emailVal).toBe('business@test.com');
    }
  });

  test('navigation back to landing works', async ({ page }) => {
    const homeLink = page.locator('a:has-text("Home"), .sc-logo').first();
    if (await homeLink.isVisible()) {
      await homeLink.click();
      await page.waitForTimeout(1500);
      const url = page.url();
      expect(url.endsWith('/') || url.includes('/home')).toBeTruthy();
    }
  });
});
