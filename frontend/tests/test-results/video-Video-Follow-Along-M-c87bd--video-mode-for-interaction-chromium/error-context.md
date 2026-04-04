# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: video.spec.js >> Video Follow-Along Mode >> Video Interaction >> voice bar appears in video mode for interaction
- Location: specs/video.spec.js:124:5

# Error details

```
Error: page.goto: net::ERR_CONNECTION_REFUSED at http://localhost:3001/login
Call log:
  - navigating to "http://localhost:3001/login", waiting until "load"

```

# Page snapshot

```yaml
- generic [ref=e3]:
  - generic [ref=e6]:
    - heading "This site can’t be reached" [level=1] [ref=e7]
    - paragraph [ref=e8]:
      - strong [ref=e9]: localhost
      - text: refused to connect.
    - generic [ref=e10]:
      - paragraph [ref=e11]: "Try:"
      - list [ref=e12]:
        - listitem [ref=e13]: Checking the connection
        - listitem [ref=e14]:
          - link "Checking the proxy and the firewall" [ref=e15] [cursor=pointer]:
            - /url: "#buttons"
    - generic [ref=e16]: ERR_CONNECTION_REFUSED
  - generic [ref=e17]:
    - button "Reload" [ref=e19] [cursor=pointer]
    - button "Details" [ref=e20] [cursor=pointer]
```

# Test source

```ts
  1   | import { test, expect } from '@playwright/test';
  2   | import { SEL } from '../helpers/selectors.js';
  3   | 
  4   | async function loginAndGoHome(page) {
> 5   |   await page.goto('/login');
      |              ^ Error: page.goto: net::ERR_CONNECTION_REFUSED at http://localhost:3001/login
  6   |   await page.fill(SEL.auth.loginEmail, 'ishita@seekcapacity.ai');
  7   |   await page.fill(SEL.auth.loginPassword, 'ishita123');
  8   |   await page.click(SEL.auth.loginBtn);
  9   |   await page.waitForURL('**/home', { timeout: 15_000 });
  10  | }
  11  | 
  12  | async function navigateToFirstCourseAndPlay(page) {
  13  |   await loginAndGoHome(page);
  14  |   await page.waitForTimeout(3000);
  15  |   const grid = page.locator(SEL.home.coursesGrid);
  16  |   const card = grid.locator('.ccard').first();
  17  |   if (await card.isVisible()) {
  18  |     await card.click();
  19  |     await page.waitForURL('**/courses/**', { timeout: 10_000 });
  20  |     await page.waitForTimeout(2000);
  21  |   }
  22  | }
  23  | 
  24  | test.describe('Video Follow-Along Mode', () => {
  25  | 
  26  |   // ──────────── Video Entry ────────────
  27  | 
  28  |   test.describe('Starting Video Mode', () => {
  29  |     test('play button on course page initiates video or session', async ({ page }) => {
  30  |       await navigateToFirstCourseAndPlay(page);
  31  |       const playBtn = page.locator(SEL.course.playBtn);
  32  |       if (await playBtn.isVisible()) {
  33  |         await playBtn.click();
  34  |         await page.waitForTimeout(8000);
  35  |         const overlay = page.locator(SEL.video.overlay);
  36  |         const teaching = page.locator(SEL.screens.teaching);
  37  |         const hasVideo = await overlay.isVisible();
  38  |         const hasTeaching = await teaching.isVisible();
  39  |         expect(hasVideo || hasTeaching || page.url().includes('/session')).toBeTruthy();
  40  |       }
  41  |     });
  42  |   });
  43  | 
  44  |   // ──────────── Video Overlay ────────────
  45  | 
  46  |   test.describe('Video Overlay', () => {
  47  |     test.beforeEach(async ({ page }) => {
  48  |       await navigateToFirstCourseAndPlay(page);
  49  |       const playBtn = page.locator(SEL.course.playBtn);
  50  |       if (await playBtn.isVisible()) {
  51  |         await playBtn.click();
  52  |         await page.waitForTimeout(8000);
  53  |       }
  54  |     });
  55  | 
  56  |     test('video overlay renders if video mode entered', async ({ page }) => {
  57  |       const overlay = page.locator(SEL.video.overlay);
  58  |       if (await overlay.isVisible()) {
  59  |         await expect(overlay).toBeVisible();
  60  |       }
  61  |     });
  62  | 
  63  |     test('close button exits video mode', async ({ page }) => {
  64  |       const overlay = page.locator(SEL.video.overlay);
  65  |       if (await overlay.isVisible()) {
  66  |         const closeBtn = page.locator(SEL.video.closeBtn);
  67  |         await closeBtn.click();
  68  |         await page.waitForTimeout(2000);
  69  |         await expect(overlay).toBeHidden();
  70  |       }
  71  |     });
  72  | 
  73  |     test('video wrap area exists', async ({ page }) => {
  74  |       const overlay = page.locator(SEL.video.overlay);
  75  |       if (await overlay.isVisible()) {
  76  |         const vidWrap = page.locator(SEL.video.vidWrap);
  77  |         await expect(vidWrap).toBeVisible();
  78  |       }
  79  |     });
  80  |   });
  81  | 
  82  |   // ──────────── Video Playlist ────────────
  83  | 
  84  |   test.describe('Video Playlist', () => {
  85  |     test('playlist panel shows if multiple lessons', async ({ page }) => {
  86  |       await navigateToFirstCourseAndPlay(page);
  87  |       const playBtn = page.locator(SEL.course.playBtn);
  88  |       if (await playBtn.isVisible()) {
  89  |         await playBtn.click();
  90  |         await page.waitForTimeout(5000);
  91  |         const playlist = page.locator(SEL.video.playlist);
  92  |         const isVisible = await playlist.isVisible();
  93  |         expect(typeof isVisible).toBe('boolean');
  94  |       }
  95  |     });
  96  | 
  97  |     test('playlist count shows correct lesson count', async ({ page }) => {
  98  |       await navigateToFirstCourseAndPlay(page);
  99  |       const playBtn = page.locator(SEL.course.playBtn);
  100 |       if (await playBtn.isVisible()) {
  101 |         await playBtn.click();
  102 |         await page.waitForTimeout(5000);
  103 |         const count = page.locator(SEL.video.playlistCount);
  104 |         if (await count.isVisible()) {
  105 |           const text = await count.textContent();
```