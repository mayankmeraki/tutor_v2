# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: course.spec.js >> Course Detail Page >> play button starts a session or video
- Location: specs/course.spec.js:77:3

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
  12  | async function navigateToFirstCourse(page) {
  13  |   await loginAndGoHome(page);
  14  |   await page.waitForTimeout(3000);
  15  |   const grid = page.locator(SEL.home.coursesGrid);
  16  |   const card = grid.locator('.ccard').first();
  17  |   if (await card.isVisible()) {
  18  |     await card.click();
  19  |     await page.waitForURL('**/courses/**', { timeout: 10_000 });
  20  |   }
  21  | }
  22  | 
  23  | test.describe('Course Detail Page', () => {
  24  | 
  25  |   test.beforeEach(async ({ page }) => {
  26  |     await navigateToFirstCourse(page);
  27  |   });
  28  | 
  29  |   // ──────────── Layout ────────────
  30  | 
  31  |   test('course screen is visible', async ({ page }) => {
  32  |     await expect(page.locator(SEL.screens.course)).toBeVisible();
  33  |   });
  34  | 
  35  |   test('displays course title', async ({ page }) => {
  36  |     const title = page.locator(SEL.course.title);
  37  |     await expect(title).toBeVisible();
  38  |     const text = await title.textContent();
  39  |     expect(text.length).toBeGreaterThan(0);
  40  |   });
  41  | 
  42  |   test('displays course description', async ({ page }) => {
  43  |     const desc = page.locator(SEL.course.description);
  44  |     await expect(desc).toBeVisible();
  45  |     const text = await desc.textContent();
  46  |     expect(text.length).toBeGreaterThan(0);
  47  |   });
  48  | 
  49  |   test('displays course tag', async ({ page }) => {
  50  |     const tag = page.locator(SEL.course.tag);
  51  |     if (await tag.isVisible()) {
  52  |       const text = await tag.textContent();
  53  |       expect(text.length).toBeGreaterThan(0);
  54  |     }
  55  |   });
  56  | 
  57  |   test('displays lesson and module counts', async ({ page }) => {
  58  |     const lessons = page.locator(SEL.course.lessonsCount);
  59  |     const modules = page.locator(SEL.course.modulesCount);
  60  |     if (await lessons.isVisible()) {
  61  |       const text = await lessons.textContent();
  62  |       expect(text.length).toBeGreaterThan(0);
  63  |     }
  64  |     if (await modules.isVisible()) {
  65  |       const text = await modules.textContent();
  66  |       expect(text.length).toBeGreaterThan(0);
  67  |     }
  68  |   });
  69  | 
  70  |   // ──────────── Play Button ────────────
  71  | 
  72  |   test('play button is visible', async ({ page }) => {
  73  |     const playBtn = page.locator(SEL.course.playBtn);
  74  |     await expect(playBtn).toBeVisible();
  75  |   });
  76  | 
  77  |   test('play button starts a session or video', async ({ page }) => {
  78  |     const playBtn = page.locator(SEL.course.playBtn);
  79  |     await playBtn.click();
  80  |     await page.waitForTimeout(5000);
  81  |     const url = page.url();
  82  |     const teaching = page.locator(SEL.screens.teaching);
  83  |     const videoOverlay = page.locator(SEL.video.overlay);
  84  |     const isSession = url.includes('/session');
  85  |     const isTeaching = await teaching.isVisible();
  86  |     const isVideo = await videoOverlay.isVisible();
  87  |     expect(isSession || isTeaching || isVideo).toBeTruthy();
  88  |   });
  89  | 
  90  |   // ──────────── Filmstrip ────────────
  91  | 
  92  |   test('filmstrip renders lesson cards', async ({ page }) => {
  93  |     const filmstrip = page.locator(SEL.course.filmstrip);
  94  |     await page.waitForTimeout(2000);
  95  |     if (await filmstrip.isVisible()) {
  96  |       const cards = filmstrip.locator('[class*="fs-"]');
  97  |       const count = await cards.count();
  98  |       expect(count).toBeGreaterThan(0);
  99  |     }
  100 |   });
  101 | 
  102 |   test('clicking a filmstrip card shows lesson detail', async ({ page }) => {
  103 |     const filmstrip = page.locator(SEL.course.filmstrip);
  104 |     await page.waitForTimeout(2000);
  105 |     if (await filmstrip.isVisible()) {
  106 |       const firstCard = filmstrip.locator('[class*="fs-card"], [class*="fs-item"]').first();
  107 |       if (await firstCard.isVisible()) {
  108 |         await firstCard.click();
  109 |         await page.waitForTimeout(1000);
```