import { test, expect } from '@playwright/test';

test.describe('Smoke tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => localStorage.clear());
    await page.goto('/');
  });

  test('landing renders for unauthenticated users', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /one tutor/i })).toBeVisible();
    await expect(page.getByPlaceholder(/what do you want to learn/i)).toBeVisible();
  });

  test('Sign in button navigates to /login', async ({ page }) => {
    await page.getByRole('button', { name: /sign in/i }).first().click();
    await page.waitForURL('**/login');
    await expect(page.getByRole('heading', { name: /welcome back/i })).toBeVisible();
  });

  test('For Institutions link navigates correctly', async ({ page }) => {
    await page.getByRole('link', { name: /for institutions/i }).first().click();
    await page.waitForURL('**/for-business');
    await expect(page.getByRole('heading', { name: /your curriculum/i })).toBeVisible();
  });

  test('Protected routes redirect to /login', async ({ page }) => {
    await page.goto('/home');
    await page.waitForURL('**/login');
  });
});
