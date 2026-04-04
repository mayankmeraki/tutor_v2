# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: home.spec.js >> Home / Browse Screen >> displays user avatar
- Location: specs/home.spec.js:40:3

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
  4   | /**
  5   |  * Reusable login fixture — logs in before each test.
  6   |  */
  7   | async function loginAndGoHome(page) {
  8   |   await page.goto('/login');
  9   |   await page.fill(SEL.auth.loginEmail, 'ishita@seekcapacity.ai');
  10  |   await page.fill(SEL.auth.loginPassword, 'ishita123');
  11  |   await page.click(SEL.auth.loginBtn);
> 12  |   await page.waitForURL('**/home', { timeout: 15_000 });
      |              ^ TimeoutError: page.waitForURL: Timeout 15000ms exceeded.
  13  | }
  14  | 
  15  | test.describe('Home / Browse Screen', () => {
  16  | 
  17  |   test.beforeEach(async ({ page }) => {
  18  |     await loginAndGoHome(page);
  19  |   });
  20  | 
  21  |   // ──────────── Layout ────────────
  22  | 
  23  |   test('browse screen is visible after login', async ({ page }) => {
  24  |     await expect(page.locator(SEL.screens.browse)).toBeVisible();
  25  |     await expect(page.locator(SEL.screens.landing)).toBeHidden();
  26  |   });
  27  | 
  28  |   test('displays user greeting', async ({ page }) => {
  29  |     const greeting = page.locator(SEL.home.greeting);
  30  |     await expect(greeting).toBeVisible();
  31  |     const text = await greeting.textContent();
  32  |     expect(text.length).toBeGreaterThan(0);
  33  |   });
  34  | 
  35  |   test('displays user name in header', async ({ page }) => {
  36  |     const name = page.locator(SEL.home.userName);
  37  |     await expect(name).toBeVisible();
  38  |   });
  39  | 
  40  |   test('displays user avatar', async ({ page }) => {
  41  |     const avatar = page.locator(SEL.home.avatar);
  42  |     await expect(avatar).toBeVisible();
  43  |   });
  44  | 
  45  |   test('logout button is visible', async ({ page }) => {
  46  |     await expect(page.locator(SEL.home.logoutBtn)).toBeVisible();
  47  |   });
  48  | 
  49  |   // ──────────── Euler Input (Search) ────────────
  50  | 
  51  |   test('euler input is visible and accepts text', async ({ page }) => {
  52  |     const input = page.locator(SEL.home.eulerInput);
  53  |     await expect(input).toBeVisible();
  54  |     await page.fill(SEL.home.eulerInput, 'teach me about derivatives');
  55  |     const val = await page.inputValue(SEL.home.eulerInput);
  56  |     expect(val).toBe('teach me about derivatives');
  57  |   });
  58  | 
  59  |   test('euler send button is clickable', async ({ page }) => {
  60  |     await expect(page.locator(SEL.home.eulerSendBtn)).toBeVisible();
  61  |   });
  62  | 
  63  |   test('euler chips are displayed', async ({ page }) => {
  64  |     const chips = page.locator(SEL.home.eulerChips);
  65  |     const count = await chips.count();
  66  |     expect(count).toBeGreaterThanOrEqual(0);
  67  |   });
  68  | 
  69  |   test('clicking euler chip fills the input', async ({ page }) => {
  70  |     const chips = page.locator(SEL.home.eulerChips);
  71  |     const count = await chips.count();
  72  |     if (count > 0) {
  73  |       const chipText = await chips.first().textContent();
  74  |       await chips.first().click();
  75  |       await page.waitForTimeout(500);
  76  |       const val = await page.inputValue(SEL.home.eulerInput);
  77  |       expect(val.length).toBeGreaterThan(0);
  78  |     }
  79  |   });
  80  | 
  81  |   // ──────────── Tabs ────────────
  82  | 
  83  |   test('home tab is active by default', async ({ page }) => {
  84  |     const homeTab = page.locator(SEL.home.tabHome);
  85  |     if (await homeTab.isVisible()) {
  86  |       await expect(homeTab).toHaveClass(/active/);
  87  |     }
  88  |   });
  89  | 
  90  |   test('clicking My Stuff tab switches panel', async ({ page }) => {
  91  |     const stuffTab = page.locator(SEL.home.tabStuff);
  92  |     if (await stuffTab.isVisible()) {
  93  |       await stuffTab.click();
  94  |       await page.waitForTimeout(500);
  95  |       const tabStuff = page.locator('#tab-stuff');
  96  |       await expect(tabStuff).toBeVisible();
  97  |     }
  98  |   });
  99  | 
  100 |   test('switching back to Home tab works', async ({ page }) => {
  101 |     const stuffTab = page.locator(SEL.home.tabStuff);
  102 |     const homeTab = page.locator(SEL.home.tabHome);
  103 |     if (await stuffTab.isVisible() && await homeTab.isVisible()) {
  104 |       await stuffTab.click();
  105 |       await page.waitForTimeout(300);
  106 |       await homeTab.click();
  107 |       await page.waitForTimeout(300);
  108 |       const tabHome = page.locator('#tab-home');
  109 |       await expect(tabHome).toBeVisible();
  110 |     }
  111 |   });
  112 | 
```