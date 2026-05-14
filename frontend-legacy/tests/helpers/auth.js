/**
 * Auth helpers for Playwright tests.
 * Handles login/signup and injects auth state so tests don't repeat the login flow.
 */

const TEST_USER = {
  name: 'Test User',
  email: `testuser_${Date.now()}@capacity.test`,
  password: 'TestPass123!',
};

const EXISTING_USER = {
  email: 'ishita@seekcapacity.ai',
  password: 'ishita123',
  name: 'Ishita',
};

/**
 * Sign up a fresh test user via the UI.
 */
async function signupViaUI(page) {
  await page.goto('/login');
  await page.click('[data-tab="signup"]');
  await page.fill('#signup-name', TEST_USER.name);
  await page.fill('#signup-email', TEST_USER.email);
  await page.fill('#signup-password', TEST_USER.password);
  await page.click('#btn-signup');
  await page.waitForURL('**/home', { timeout: 10_000 });
  return TEST_USER;
}

/**
 * Log in with existing credentials via the UI.
 */
async function loginViaUI(page, user = EXISTING_USER) {
  await page.goto('/login');
  await page.waitForSelector('#login-email', { state: 'visible' });
  await page.fill('#login-email', user.email);
  await page.fill('#login-password', user.password);
  await page.click('#btn-login');
  await page.waitForURL('**/home', { timeout: 10_000 });
  return user;
}

/**
 * Inject auth token into localStorage so tests skip the login page.
 * Call BEFORE page.goto().
 */
async function injectAuth(page, baseURL) {
  await page.goto(baseURL + '/login');
  await page.waitForSelector('#login-email', { state: 'visible' });
  await page.fill('#login-email', EXISTING_USER.email);
  await page.fill('#login-password', EXISTING_USER.password);
  await page.click('#btn-login');
  await page.waitForURL('**/home', { timeout: 10_000 });
}

/**
 * Check if currently logged in by evaluating localStorage.
 */
async function isLoggedIn(page) {
  return page.evaluate(() => !!localStorage.getItem('capacity_token'));
}

/**
 * Logout via the UI button.
 */
async function logout(page) {
  const logoutBtn = page.locator('#btn-logout');
  if (await logoutBtn.isVisible()) {
    await logoutBtn.click();
  }
}

export { TEST_USER, EXISTING_USER, signupViaUI, loginViaUI, injectAuth, isLoggedIn, logout };
