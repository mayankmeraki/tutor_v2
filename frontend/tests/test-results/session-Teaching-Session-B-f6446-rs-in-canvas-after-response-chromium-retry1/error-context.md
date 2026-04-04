# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: session.spec.js >> Teaching Session >> Board & Streaming Content >> teaching content appears in canvas after response
- Location: specs/session.spec.js:97:5

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
  4   | async function loginAndGoHome(page) {
  5   |   await page.goto('/login');
  6   |   await page.fill(SEL.auth.loginEmail, 'ishita@seekcapacity.ai');
  7   |   await page.fill(SEL.auth.loginPassword, 'ishita123');
  8   |   await page.click(SEL.auth.loginBtn);
> 9   |   await page.waitForURL('**/home', { timeout: 15_000 });
      |              ^ TimeoutError: page.waitForURL: Timeout 15000ms exceeded.
  10  | }
  11  | 
  12  | async function startOnDemandSession(page) {
  13  |   await loginAndGoHome(page);
  14  |   await page.fill(SEL.home.eulerInput, 'explain what is a derivative in calculus');
  15  |   await page.click(SEL.home.eulerSendBtn);
  16  |   await page.waitForTimeout(8000);
  17  | }
  18  | 
  19  | test.describe('Teaching Session', () => {
  20  | 
  21  |   // ──────────── Session Start ────────────
  22  | 
  23  |   test.describe('Session Start', () => {
  24  |     test('starting from euler input shows prep overlay then teaching', async ({ page }) => {
  25  |       await startOnDemandSession(page);
  26  |       const teaching = page.locator(SEL.screens.teaching);
  27  |       const prep = page.locator(SEL.teaching.prepOverlay);
  28  |       const isTeaching = await teaching.isVisible();
  29  |       const isPrepping = await prep.isVisible();
  30  |       expect(isTeaching || isPrepping).toBeTruthy();
  31  |     });
  32  | 
  33  |     test('URL updates to /session/:id', async ({ page }) => {
  34  |       await startOnDemandSession(page);
  35  |       await page.waitForTimeout(3000);
  36  |       expect(page.url()).toMatch(/\/session\/.+/);
  37  |     });
  38  | 
  39  |     test('session timer starts counting', async ({ page }) => {
  40  |       await startOnDemandSession(page);
  41  |       const teaching = page.locator(SEL.screens.teaching);
  42  |       if (await teaching.isVisible()) {
  43  |         const timer = page.locator(SEL.teaching.timer);
  44  |         await page.waitForTimeout(3000);
  45  |         if (await timer.isVisible()) {
  46  |           const text = await timer.textContent();
  47  |           expect(text).toBeTruthy();
  48  |         }
  49  |       }
  50  |     });
  51  |   });
  52  | 
  53  |   // ──────────── Teaching Layout ────────────
  54  | 
  55  |   test.describe('Teaching Layout', () => {
  56  |     test.beforeEach(async ({ page }) => {
  57  |       await startOnDemandSession(page);
  58  |     });
  59  | 
  60  |     test('top bar is visible with course title', async ({ page }) => {
  61  |       const topBar = page.locator(SEL.teaching.topBar);
  62  |       if (await topBar.isVisible()) {
  63  |         await expect(topBar).toBeVisible();
  64  |       }
  65  |     });
  66  | 
  67  |     test('chat panel exists', async ({ page }) => {
  68  |       const chatPanel = page.locator(SEL.teaching.chatPanel);
  69  |       const isVisible = await chatPanel.isVisible();
  70  |       expect(typeof isVisible).toBe('boolean');
  71  |     });
  72  | 
  73  |     test('board panel exists', async ({ page }) => {
  74  |       const boardPanel = page.locator(SEL.teaching.boardPanel);
  75  |       const isVisible = await boardPanel.isVisible();
  76  |       expect(typeof isVisible).toBe('boolean');
  77  |     });
  78  | 
  79  |     test('canvas stream area renders', async ({ page }) => {
  80  |       const canvas = page.locator(SEL.teaching.canvasStream);
  81  |       if (await canvas.isVisible()) {
  82  |         await expect(canvas).toBeVisible();
  83  |       }
  84  |     });
  85  | 
  86  |     test('back button is available', async ({ page }) => {
  87  |       const backBtn = page.locator(SEL.teaching.backBtn);
  88  |       if (await backBtn.isVisible()) {
  89  |         await expect(backBtn).toBeVisible();
  90  |       }
  91  |     });
  92  |   });
  93  | 
  94  |   // ──────────── Board Content ────────────
  95  | 
  96  |   test.describe('Board & Streaming Content', () => {
  97  |     test('teaching content appears in canvas after response', async ({ page }) => {
  98  |       await startOnDemandSession(page);
  99  |       await page.waitForTimeout(15_000);
  100 |       const canvas = page.locator(SEL.teaching.canvasStream);
  101 |       if (await canvas.isVisible()) {
  102 |         const html = await canvas.innerHTML();
  103 |         expect(html.length).toBeGreaterThan(0);
  104 |       }
  105 |     });
  106 | 
  107 |     test('spotlight content area renders on board interaction', async ({ page }) => {
  108 |       await startOnDemandSession(page);
  109 |       await page.waitForTimeout(10_000);
```