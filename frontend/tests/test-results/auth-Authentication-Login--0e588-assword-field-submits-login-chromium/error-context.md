# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: auth.spec.js >> Authentication >> Login >> pressing Enter in password field submits login
- Location: specs/auth.spec.js:58:5

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
        - textbox "Password" [active] [ref=e16]: ishita123
      - generic [ref=e17]: Invalid email or password
      - button "Sign In" [ref=e18] [cursor=pointer]
```

# Test source

```ts
  1   | import { test, expect } from '@playwright/test';
  2   | import { SEL } from '../helpers/selectors.js';
  3   | 
  4   | test.describe('Authentication', () => {
  5   | 
  6   |   test.beforeEach(async ({ page }) => {
  7   |     await page.goto('/');
  8   |     await page.evaluate(() => localStorage.clear());
  9   |     await page.goto('/');
  10  |   });
  11  | 
  12  |   // ──────────── Login ────────────
  13  | 
  14  |   test.describe('Login', () => {
  15  |     test('shows login panel with email and password fields', async ({ page }) => {
  16  |       await page.goto('/login');
  17  |       await expect(page.locator(SEL.auth.loginEmail)).toBeVisible();
  18  |       await expect(page.locator(SEL.auth.loginPassword)).toBeVisible();
  19  |       await expect(page.locator(SEL.auth.loginBtn)).toBeVisible();
  20  |     });
  21  | 
  22  |     test('sign-in tab is active by default', async ({ page }) => {
  23  |       await page.goto('/login');
  24  |       const tab = page.locator(SEL.auth.tabSignIn);
  25  |       await expect(tab).toHaveClass(/active/);
  26  |     });
  27  | 
  28  |     test('login with valid credentials redirects to /home', async ({ page }) => {
  29  |       await page.goto('/login');
  30  |       await page.fill(SEL.auth.loginEmail, 'ishita@seekcapacity.ai');
  31  |       await page.fill(SEL.auth.loginPassword, 'ishita123');
  32  |       await page.click(SEL.auth.loginBtn);
  33  |       await page.waitForURL('**/home', { timeout: 15_000 });
  34  |       expect(page.url()).toContain('/home');
  35  |       const token = await page.evaluate(() => localStorage.getItem('capacity_token'));
  36  |       expect(token).toBeTruthy();
  37  |     });
  38  | 
  39  |     test('login with wrong password shows error', async ({ page }) => {
  40  |       await page.goto('/login');
  41  |       await page.fill(SEL.auth.loginEmail, 'ishita@seekcapacity.ai');
  42  |       await page.fill(SEL.auth.loginPassword, 'wrongpassword999');
  43  |       await page.click(SEL.auth.loginBtn);
  44  |       await page.waitForTimeout(2000);
  45  |       const status = page.locator(SEL.auth.loginStatus);
  46  |       await expect(status).not.toBeEmpty();
  47  |     });
  48  | 
  49  |     test('login with empty fields shows validation feedback', async ({ page }) => {
  50  |       await page.goto('/login');
  51  |       await page.click(SEL.auth.loginBtn);
  52  |       await page.waitForTimeout(1000);
  53  |       const status = page.locator(SEL.auth.loginStatus);
  54  |       const statusText = await status.textContent();
  55  |       expect(statusText.length).toBeGreaterThan(0);
  56  |     });
  57  | 
  58  |     test('pressing Enter in password field submits login', async ({ page }) => {
  59  |       await page.goto('/login');
  60  |       await page.fill(SEL.auth.loginEmail, 'ishita@seekcapacity.ai');
  61  |       await page.fill(SEL.auth.loginPassword, 'ishita123');
  62  |       await page.press(SEL.auth.loginPassword, 'Enter');
> 63  |       await page.waitForURL('**/home', { timeout: 15_000 });
      |                  ^ TimeoutError: page.waitForURL: Timeout 15000ms exceeded.
  64  |       expect(page.url()).toContain('/home');
  65  |     });
  66  |   });
  67  | 
  68  |   // ──────────── Signup ────────────
  69  | 
  70  |   test.describe('Signup', () => {
  71  |     test('switch to signup tab shows signup form', async ({ page }) => {
  72  |       await page.goto('/login');
  73  |       await page.click(SEL.auth.tabSignUp);
  74  |       await expect(page.locator(SEL.auth.signupName)).toBeVisible();
  75  |       await expect(page.locator(SEL.auth.signupEmail)).toBeVisible();
  76  |       await expect(page.locator(SEL.auth.signupPassword)).toBeVisible();
  77  |       await expect(page.locator(SEL.auth.signupBtn)).toBeVisible();
  78  |     });
  79  | 
  80  |     test('signup with short password shows error', async ({ page }) => {
  81  |       await page.goto('/login');
  82  |       await page.click(SEL.auth.tabSignUp);
  83  |       await page.fill(SEL.auth.signupName, 'Tester');
  84  |       await page.fill(SEL.auth.signupEmail, `short_${Date.now()}@test.com`);
  85  |       await page.fill(SEL.auth.signupPassword, 'abc');
  86  |       await page.click(SEL.auth.signupBtn);
  87  |       await page.waitForTimeout(1500);
  88  |       const status = page.locator(SEL.auth.signupStatus);
  89  |       const statusText = await status.textContent();
  90  |       expect(statusText.length).toBeGreaterThan(0);
  91  |     });
  92  | 
  93  |     test('signup with valid data creates account and redirects', async ({ page }) => {
  94  |       const uniqueEmail = `pw_test_${Date.now()}@capacity.test`;
  95  |       await page.goto('/login');
  96  |       await page.click(SEL.auth.tabSignUp);
  97  |       await page.fill(SEL.auth.signupName, 'PW Test User');
  98  |       await page.fill(SEL.auth.signupEmail, uniqueEmail);
  99  |       await page.fill(SEL.auth.signupPassword, 'TestPass123!');
  100 |       await page.click(SEL.auth.signupBtn);
  101 |       await page.waitForURL('**/home', { timeout: 15_000 });
  102 |       expect(page.url()).toContain('/home');
  103 |     });
  104 |   });
  105 | 
  106 |   // ──────────── Logout ────────────
  107 | 
  108 |   test.describe('Logout', () => {
  109 |     test('logout clears token and redirects to landing', async ({ page }) => {
  110 |       await page.goto('/login');
  111 |       await page.fill(SEL.auth.loginEmail, 'ishita@seekcapacity.ai');
  112 |       await page.fill(SEL.auth.loginPassword, 'ishita123');
  113 |       await page.click(SEL.auth.loginBtn);
  114 |       await page.waitForURL('**/home', { timeout: 15_000 });
  115 | 
  116 |       await page.click(SEL.home.logoutBtn);
  117 |       await page.waitForTimeout(1500);
  118 |       const token = await page.evaluate(() => localStorage.getItem('capacity_token'));
  119 |       expect(token).toBeFalsy();
  120 |     });
  121 |   });
  122 | 
  123 |   // ──────────── Protected Routes ────────────
  124 | 
  125 |   test.describe('Protected routes', () => {
  126 |     test('/home redirects to landing when not logged in', async ({ page }) => {
  127 |       await page.evaluate(() => localStorage.clear());
  128 |       await page.goto('/home');
  129 |       await page.waitForTimeout(2000);
  130 |       const url = page.url();
  131 |       expect(url.endsWith('/') || url.includes('/login')).toBeTruthy();
  132 |     });
  133 | 
  134 |     test('/courses/1 redirects when not logged in', async ({ page }) => {
  135 |       await page.evaluate(() => localStorage.clear());
  136 |       await page.goto('/courses/1');
  137 |       await page.waitForTimeout(2000);
  138 |       const url = page.url();
  139 |       expect(url.endsWith('/') || url.includes('/login')).toBeTruthy();
  140 |     });
  141 | 
  142 |     test('/session redirects when not logged in', async ({ page }) => {
  143 |       await page.evaluate(() => localStorage.clear());
  144 |       await page.goto('/session');
  145 |       await page.waitForTimeout(2000);
  146 |       const url = page.url();
  147 |       expect(url.endsWith('/') || url.includes('/login') || url.includes('/home')).toBeTruthy();
  148 |     });
  149 | 
  150 |     test('logged-in user visiting /login is redirected to /home', async ({ page }) => {
  151 |       await page.goto('/login');
  152 |       await page.fill(SEL.auth.loginEmail, 'ishita@seekcapacity.ai');
  153 |       await page.fill(SEL.auth.loginPassword, 'ishita123');
  154 |       await page.click(SEL.auth.loginBtn);
  155 |       await page.waitForURL('**/home', { timeout: 15_000 });
  156 | 
  157 |       await page.goto('/login');
  158 |       await page.waitForTimeout(2000);
  159 |       expect(page.url()).toContain('/home');
  160 |     });
  161 | 
  162 |     test('logged-in user visiting / is redirected to /home', async ({ page }) => {
  163 |       await page.goto('/login');
```