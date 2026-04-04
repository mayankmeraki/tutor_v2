# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: navigation.spec.js >> Navigation & Routing >> Authenticated Routes >> /tutor shows browse screen
- Location: specs/navigation.spec.js:68:5

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
  12  | test.describe('Navigation & Routing', () => {
  13  | 
  14  |   // ──────────── Route Resolution ────────────
  15  | 
  16  |   test.describe('Public Routes', () => {
  17  |     test.beforeEach(async ({ page }) => {
  18  |       await page.evaluate(() => localStorage.clear());
  19  |     });
  20  | 
  21  |     test('/ shows landing for unauthenticated user', async ({ page }) => {
  22  |       await page.goto('/');
  23  |       await expect(page.locator(SEL.screens.landing)).toBeVisible();
  24  |     });
  25  | 
  26  |     test('/login shows login panel', async ({ page }) => {
  27  |       await page.goto('/login');
  28  |       await expect(page.locator(SEL.screens.login)).toBeVisible();
  29  |     });
  30  | 
  31  |     test('/for-business shows business screen', async ({ page }) => {
  32  |       await page.goto('/for-business');
  33  |       await expect(page.locator(SEL.screens.business)).toBeVisible();
  34  |     });
  35  | 
  36  |     test('unknown route redirects to / or /login', async ({ page }) => {
  37  |       await page.goto('/this-route-does-not-exist');
  38  |       await page.waitForTimeout(2000);
  39  |       const url = page.url();
  40  |       expect(url.endsWith('/') || url.includes('/login') || url.includes('/home')).toBeTruthy();
  41  |     });
  42  |   });
  43  | 
  44  |   // ──────────── Authenticated Routes ────────────
  45  | 
  46  |   test.describe('Authenticated Routes', () => {
  47  |     test.beforeEach(async ({ page }) => {
  48  |       await login(page);
  49  |     });
  50  | 
  51  |     test('/home shows browse screen', async ({ page }) => {
  52  |       await page.goto('/home');
  53  |       await expect(page.locator(SEL.screens.browse)).toBeVisible();
  54  |     });
  55  | 
  56  |     test('/dashboard is alias for /home', async ({ page }) => {
  57  |       await page.goto('/dashboard');
  58  |       await page.waitForTimeout(1000);
  59  |       await expect(page.locator(SEL.screens.browse)).toBeVisible();
  60  |     });
  61  | 
  62  |     test('/courses shows browse screen', async ({ page }) => {
  63  |       await page.goto('/courses');
  64  |       await page.waitForTimeout(1000);
  65  |       await expect(page.locator(SEL.screens.browse)).toBeVisible();
  66  |     });
  67  | 
  68  |     test('/tutor shows browse screen', async ({ page }) => {
  69  |       await page.goto('/tutor');
  70  |       await page.waitForTimeout(1000);
  71  |       await expect(page.locator(SEL.screens.browse)).toBeVisible();
  72  |     });
  73  | 
  74  |     test('/session redirects to /home', async ({ page }) => {
  75  |       await page.goto('/session');
  76  |       await page.waitForTimeout(2000);
  77  |       expect(page.url()).toContain('/home');
  78  |     });
  79  |   });
  80  | 
  81  |   // ──────────── Browser History ────────────
  82  | 
  83  |   test.describe('Browser History (Back/Forward)', () => {
  84  |     test('back from course detail returns to home', async ({ page }) => {
  85  |       await login(page);
  86  |       await page.waitForTimeout(3000);
  87  |       const grid = page.locator(SEL.home.coursesGrid);
  88  |       const card = grid.locator('.ccard').first();
  89  |       if (await card.isVisible()) {
  90  |         await card.click();
  91  |         await page.waitForURL('**/courses/**', { timeout: 10_000 });
  92  |         await expect(page.locator(SEL.screens.course)).toBeVisible();
  93  | 
  94  |         await page.goBack();
  95  |         await page.waitForTimeout(2000);
  96  |         expect(page.url()).toContain('/home');
  97  |         await expect(page.locator(SEL.screens.browse)).toBeVisible();
  98  |       }
  99  |     });
  100 | 
  101 |     test('forward after back restores course page', async ({ page }) => {
  102 |       await login(page);
  103 |       await page.waitForTimeout(3000);
  104 |       const grid = page.locator(SEL.home.coursesGrid);
  105 |       const card = grid.locator('.ccard').first();
  106 |       if (await card.isVisible()) {
  107 |         await card.click();
  108 |         await page.waitForURL('**/courses/**', { timeout: 10_000 });
  109 |         const courseUrl = page.url();
```