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

test.describe('Session timer — engagement gating', () => {
  test('does not advance while tab is hidden', async ({ page, context }) => {
    await startOnDemandSession(page);

    const timer = page.locator(SEL.teaching.timer);
    await expect(timer).toBeVisible();

    await page.waitForTimeout(3000);
    const tEngaged = await timer.textContent();
    expect(tEngaged).not.toBe('0:00');

    const other = await context.newPage();
    await other.goto('about:blank');
    await page.waitForTimeout(5000);

    await page.bringToFront();
    await page.waitForTimeout(500);
    const tAfterHidden = await timer.textContent();

    const toSec = (s) => {
      const [m, ss] = s.split(':').map(Number);
      return m * 60 + ss;
    };
    expect(toSec(tAfterHidden) - toSec(tEngaged)).toBeLessThan(3);

    await other.close();
  });
});
