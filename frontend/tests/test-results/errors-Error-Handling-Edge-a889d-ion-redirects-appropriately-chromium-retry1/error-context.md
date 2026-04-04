# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: errors.spec.js >> Error Handling & Edge Cases >> Auth Errors >> clearing token mid-session redirects appropriately
- Location: specs/errors.spec.js:28:5

# Error details

```
TimeoutError: page.waitForURL: Timeout 15000ms exceeded.
=========================== logs ===========================
waiting for navigation to "**/home" until "load"
============================================================
```

# Page snapshot

```yaml
- generic [ref=e4]:
  - generic [ref=e5]:
    - button "Sign In" [ref=e6] [cursor=pointer]
    - button "Create Account" [ref=e7] [cursor=pointer]
  - generic [ref=e8]:
    - paragraph [ref=e9]: Log in with your account to start learning.
    - generic [ref=e10]:
      - generic [ref=e11]:
        - generic [ref=e12]: Email
        - textbox "Email" [ref=e13]:
          - /placeholder: you@example.com
          - text: ishita@seekcapacity.ai
      - generic [ref=e14]:
        - generic [ref=e15]: Password
        - textbox "Password" [ref=e16]: ishita123
      - generic [ref=e17]: Invalid email or password
      - button "Sign In" [ref=e18] [cursor=pointer]
```

# Test source

```ts
  1   | import { test, expect } from '@playwright/test';
  2   | import { SEL } from '../helpers/selectors.js';
  3   | 
  4   | async function login(page) {
  5   |   await page.goto('/login');
  6   |   await page.fill(SEL.auth.loginEmail, 'ishita@seekcapacity.ai');
  7   |   await page.fill(SEL.auth.loginPassword, 'ishita123');
  8   |   await page.click(SEL.auth.loginBtn);
> 9   |   await page.waitForURL('**/home', { timeout: 15_000 });
      |              ^ TimeoutError: page.waitForURL: Timeout 15000ms exceeded.
  10  | }
  11  | 
  12  | test.describe('Error Handling & Edge Cases', () => {
  13  | 
  14  |   // ──────────── Auth Errors ────────────
  15  | 
  16  |   test.describe('Auth Errors', () => {
  17  |     test('expired token triggers re-login flow', async ({ page }) => {
  18  |       await login(page);
  19  |       await page.evaluate(() => localStorage.setItem('capacity_token', 'expired_invalid_token'));
  20  |       await page.goto('/home');
  21  |       await page.waitForTimeout(5000);
  22  |       const url = page.url();
  23  |       const loginVisible = await page.locator(SEL.screens.login).isVisible();
  24  |       const landingVisible = await page.locator(SEL.screens.landing).isVisible();
  25  |       expect(loginVisible || landingVisible || url.includes('/login') || url.endsWith('/')).toBeTruthy();
  26  |     });
  27  | 
  28  |     test('clearing token mid-session redirects appropriately', async ({ page }) => {
  29  |       await login(page);
  30  |       await page.evaluate(() => localStorage.removeItem('capacity_token'));
  31  |       await page.goto('/home');
  32  |       await page.waitForTimeout(3000);
  33  |       const url = page.url();
  34  |       expect(url.endsWith('/') || url.includes('/login')).toBeTruthy();
  35  |     });
  36  |   });
  37  | 
  38  |   // ──────────── Network Errors ────────────
  39  | 
  40  |   test.describe('Network Resilience', () => {
  41  |     test('app handles API timeout gracefully on home', async ({ page }) => {
  42  |       await login(page);
  43  |       await page.route('**/api/v1/content/courses*', route => {
  44  |         route.abort('timedout');
  45  |       });
  46  |       await page.goto('/home');
  47  |       await page.waitForTimeout(5000);
  48  |       const browse = page.locator(SEL.screens.browse);
  49  |       await expect(browse).toBeVisible();
  50  |     });
  51  | 
  52  |     test('app handles chat API failure gracefully', async ({ page }) => {
  53  |       await login(page);
  54  |       await page.route('**/api/chat*', route => {
  55  |         route.fulfill({ status: 500, body: 'Internal Server Error' });
  56  |       });
  57  |       await page.fill(SEL.home.eulerInput, 'test network error');
  58  |       await page.click(SEL.home.eulerSendBtn);
  59  |       await page.waitForTimeout(8000);
  60  |       // should not crash — may show error or stay on same page
  61  |       const url = page.url();
  62  |       expect(url).toBeTruthy();
  63  |     });
  64  | 
  65  |     test('app handles course API 404 gracefully', async ({ page }) => {
  66  |       await login(page);
  67  |       await page.route('**/api/v1/content/course-map/999*', route => {
  68  |         route.fulfill({ status: 404, body: JSON.stringify({ detail: 'Not found' }) });
  69  |       });
  70  |       await page.goto('/courses/999');
  71  |       await page.waitForTimeout(5000);
  72  |       // should redirect to home or show error
  73  |       const browse = page.locator(SEL.screens.browse);
  74  |       const course = page.locator(SEL.screens.course);
  75  |       const isBrowse = await browse.isVisible();
  76  |       const isCourse = await course.isVisible();
  77  |       expect(isBrowse || isCourse || page.url().includes('/home')).toBeTruthy();
  78  |     });
  79  |   });
  80  | 
  81  |   // ──────────── Session Errors ────────────
  82  | 
  83  |   test.describe('Session Edge Cases', () => {
  84  |     test('invalid session ID in URL shows error or redirects', async ({ page }) => {
  85  |       await login(page);
  86  |       await page.goto('/session/nonexistent-session-xyz-999');
  87  |       await page.waitForTimeout(8000);
  88  |       const url = page.url();
  89  |       const teaching = page.locator(SEL.screens.teaching);
  90  |       const browse = page.locator(SEL.screens.browse);
  91  |       const isTeaching = await teaching.isVisible();
  92  |       const isBrowse = await browse.isVisible();
  93  |       expect(isTeaching || isBrowse || url.includes('/home')).toBeTruthy();
  94  |     });
  95  |   });
  96  | 
  97  |   // ──────────── Feedback Modal ────────────
  98  | 
  99  |   test.describe('Feedback Modal', () => {
  100 |     test('bug button opens feedback modal', async ({ page }) => {
  101 |       await login(page);
  102 |       const bugBtn = page.locator('.fb-bug-btn').first();
  103 |       if (await bugBtn.isVisible()) {
  104 |         await bugBtn.click();
  105 |         await page.waitForTimeout(1000);
  106 |         const overlay = page.locator(SEL.feedback.overlay);
  107 |         await expect(overlay).toBeVisible();
  108 |       }
  109 |     });
```