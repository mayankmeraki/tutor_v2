import { test, expect } from '@playwright/test';
import { SEL } from '../helpers/selectors.js';

test.describe('Authentication', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => localStorage.clear());
    await page.goto('/');
  });

  // ──────────── Login ────────────

  test.describe('Login', () => {
    test('shows login panel with email and password fields', async ({ page }) => {
      await page.goto('/login');
      await expect(page.locator(SEL.auth.loginEmail)).toBeVisible();
      await expect(page.locator(SEL.auth.loginPassword)).toBeVisible();
      await expect(page.locator(SEL.auth.loginBtn)).toBeVisible();
    });

    test('sign-in tab is active by default', async ({ page }) => {
      await page.goto('/login');
      const tab = page.locator(SEL.auth.tabSignIn);
      await expect(tab).toHaveClass(/active/);
    });

    test('login with valid credentials redirects to /home', async ({ page }) => {
      await page.goto('/login');
      await page.fill(SEL.auth.loginEmail, 'ishita@seekcapacity.ai');
      await page.fill(SEL.auth.loginPassword, 'ishita123');
      await page.click(SEL.auth.loginBtn);
      await page.waitForURL('**/home', { timeout: 15_000 });
      expect(page.url()).toContain('/home');
      const token = await page.evaluate(() => localStorage.getItem('capacity_token'));
      expect(token).toBeTruthy();
    });

    test('login with wrong password shows error', async ({ page }) => {
      await page.goto('/login');
      await page.fill(SEL.auth.loginEmail, 'ishita@seekcapacity.ai');
      await page.fill(SEL.auth.loginPassword, 'wrongpassword999');
      await page.click(SEL.auth.loginBtn);
      await page.waitForTimeout(2000);
      const status = page.locator(SEL.auth.loginStatus);
      await expect(status).not.toBeEmpty();
    });

    test('login with empty fields shows validation feedback', async ({ page }) => {
      await page.goto('/login');
      await page.click(SEL.auth.loginBtn);
      await page.waitForTimeout(1000);
      const status = page.locator(SEL.auth.loginStatus);
      const statusText = await status.textContent();
      expect(statusText.length).toBeGreaterThan(0);
    });

    test('pressing Enter in password field submits login', async ({ page }) => {
      await page.goto('/login');
      await page.fill(SEL.auth.loginEmail, 'ishita@seekcapacity.ai');
      await page.fill(SEL.auth.loginPassword, 'ishita123');
      await page.press(SEL.auth.loginPassword, 'Enter');
      await page.waitForURL('**/home', { timeout: 15_000 });
      expect(page.url()).toContain('/home');
    });
  });

  // ──────────── Signup ────────────

  test.describe('Signup', () => {
    test('switch to signup tab shows signup form', async ({ page }) => {
      await page.goto('/login');
      await page.click(SEL.auth.tabSignUp);
      await expect(page.locator(SEL.auth.signupName)).toBeVisible();
      await expect(page.locator(SEL.auth.signupEmail)).toBeVisible();
      await expect(page.locator(SEL.auth.signupPassword)).toBeVisible();
      await expect(page.locator(SEL.auth.signupBtn)).toBeVisible();
    });

    test('signup with short password shows error', async ({ page }) => {
      await page.goto('/login');
      await page.click(SEL.auth.tabSignUp);
      await page.fill(SEL.auth.signupName, 'Tester');
      await page.fill(SEL.auth.signupEmail, `short_${Date.now()}@test.com`);
      await page.fill(SEL.auth.signupPassword, 'abc');
      await page.click(SEL.auth.signupBtn);
      await page.waitForTimeout(1500);
      const status = page.locator(SEL.auth.signupStatus);
      const statusText = await status.textContent();
      expect(statusText.length).toBeGreaterThan(0);
    });

    test('signup with valid data creates account and redirects', async ({ page }) => {
      const uniqueEmail = `pw_test_${Date.now()}@capacity.test`;
      await page.goto('/login');
      await page.click(SEL.auth.tabSignUp);
      await page.fill(SEL.auth.signupName, 'PW Test User');
      await page.fill(SEL.auth.signupEmail, uniqueEmail);
      await page.fill(SEL.auth.signupPassword, 'TestPass123!');
      await page.click(SEL.auth.signupBtn);
      await page.waitForURL('**/home', { timeout: 15_000 });
      expect(page.url()).toContain('/home');
    });
  });

  // ──────────── Logout ────────────

  test.describe('Logout', () => {
    test('logout clears token and redirects to landing', async ({ page }) => {
      await page.goto('/login');
      await page.fill(SEL.auth.loginEmail, 'ishita@seekcapacity.ai');
      await page.fill(SEL.auth.loginPassword, 'ishita123');
      await page.click(SEL.auth.loginBtn);
      await page.waitForURL('**/home', { timeout: 15_000 });

      await page.click(SEL.home.logoutBtn);
      await page.waitForTimeout(1500);
      const token = await page.evaluate(() => localStorage.getItem('capacity_token'));
      expect(token).toBeFalsy();
    });
  });

  // ──────────── Protected Routes ────────────

  test.describe('Protected routes', () => {
    test('/home redirects to landing when not logged in', async ({ page }) => {
      await page.evaluate(() => localStorage.clear());
      await page.goto('/home');
      await page.waitForTimeout(2000);
      const url = page.url();
      expect(url.endsWith('/') || url.includes('/login')).toBeTruthy();
    });

    test('/courses/1 redirects when not logged in', async ({ page }) => {
      await page.evaluate(() => localStorage.clear());
      await page.goto('/courses/1');
      await page.waitForTimeout(2000);
      const url = page.url();
      expect(url.endsWith('/') || url.includes('/login')).toBeTruthy();
    });

    test('/session redirects when not logged in', async ({ page }) => {
      await page.evaluate(() => localStorage.clear());
      await page.goto('/session');
      await page.waitForTimeout(2000);
      const url = page.url();
      expect(url.endsWith('/') || url.includes('/login') || url.includes('/home')).toBeTruthy();
    });

    test('logged-in user visiting /login is redirected to /home', async ({ page }) => {
      await page.goto('/login');
      await page.fill(SEL.auth.loginEmail, 'ishita@seekcapacity.ai');
      await page.fill(SEL.auth.loginPassword, 'ishita123');
      await page.click(SEL.auth.loginBtn);
      await page.waitForURL('**/home', { timeout: 15_000 });

      await page.goto('/login');
      await page.waitForTimeout(2000);
      expect(page.url()).toContain('/home');
    });

    test('logged-in user visiting / is redirected to /home', async ({ page }) => {
      await page.goto('/login');
      await page.fill(SEL.auth.loginEmail, 'ishita@seekcapacity.ai');
      await page.fill(SEL.auth.loginPassword, 'ishita123');
      await page.click(SEL.auth.loginBtn);
      await page.waitForURL('**/home', { timeout: 15_000 });

      await page.goto('/');
      await page.waitForTimeout(2000);
      expect(page.url()).toContain('/home');
    });
  });
});
