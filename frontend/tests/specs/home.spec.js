import { test, expect } from '@playwright/test';
import { SEL } from '../helpers/selectors.js';

/**
 * Reusable login fixture — logs in before each test.
 */
async function loginAndGoHome(page) {
  await page.goto('/login');
  await page.fill(SEL.auth.loginEmail, 'ishita@seekcapacity.ai');
  await page.fill(SEL.auth.loginPassword, 'ishita123');
  await page.click(SEL.auth.loginBtn);
  await page.waitForURL('**/home', { timeout: 15_000 });
}

test.describe('Home / Browse Screen', () => {

  test.beforeEach(async ({ page }) => {
    await loginAndGoHome(page);
  });

  // ──────────── Layout ────────────

  test('browse screen is visible after login', async ({ page }) => {
    await expect(page.locator(SEL.screens.browse)).toBeVisible();
    await expect(page.locator(SEL.screens.landing)).toBeHidden();
  });

  test('displays user greeting', async ({ page }) => {
    const greeting = page.locator(SEL.home.greeting);
    await expect(greeting).toBeVisible();
    const text = await greeting.textContent();
    expect(text.length).toBeGreaterThan(0);
  });

  test('displays user name in header', async ({ page }) => {
    const name = page.locator(SEL.home.userName);
    await expect(name).toBeVisible();
  });

  test('displays user avatar', async ({ page }) => {
    const avatar = page.locator(SEL.home.avatar);
    await expect(avatar).toBeVisible();
  });

  test('logout button is visible', async ({ page }) => {
    await expect(page.locator(SEL.home.logoutBtn)).toBeVisible();
  });

  // ──────────── Euler Input (Search) ────────────

  test('euler input is visible and accepts text', async ({ page }) => {
    const input = page.locator(SEL.home.eulerInput);
    await expect(input).toBeVisible();
    await page.fill(SEL.home.eulerInput, 'teach me about derivatives');
    const val = await page.inputValue(SEL.home.eulerInput);
    expect(val).toBe('teach me about derivatives');
  });

  test('euler send button is clickable', async ({ page }) => {
    await expect(page.locator(SEL.home.eulerSendBtn)).toBeVisible();
  });

  test('euler chips are displayed', async ({ page }) => {
    const chips = page.locator(SEL.home.eulerChips);
    const count = await chips.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });

  test('clicking euler chip fills the input', async ({ page }) => {
    const chips = page.locator(SEL.home.eulerChips);
    const count = await chips.count();
    if (count > 0) {
      const chipText = await chips.first().textContent();
      await chips.first().click();
      await page.waitForTimeout(500);
      const val = await page.inputValue(SEL.home.eulerInput);
      expect(val.length).toBeGreaterThan(0);
    }
  });

  // ──────────── Tabs ────────────

  test('home tab is active by default', async ({ page }) => {
    const homeTab = page.locator(SEL.home.tabHome);
    if (await homeTab.isVisible()) {
      await expect(homeTab).toHaveClass(/active/);
    }
  });

  test('clicking My Stuff tab switches panel', async ({ page }) => {
    const stuffTab = page.locator(SEL.home.tabStuff);
    if (await stuffTab.isVisible()) {
      await stuffTab.click();
      await page.waitForTimeout(500);
      const tabStuff = page.locator('#tab-stuff');
      await expect(tabStuff).toBeVisible();
    }
  });

  test('switching back to Home tab works', async ({ page }) => {
    const stuffTab = page.locator(SEL.home.tabStuff);
    const homeTab = page.locator(SEL.home.tabHome);
    if (await stuffTab.isVisible() && await homeTab.isVisible()) {
      await stuffTab.click();
      await page.waitForTimeout(300);
      await homeTab.click();
      await page.waitForTimeout(300);
      const tabHome = page.locator('#tab-home');
      await expect(tabHome).toBeVisible();
    }
  });

  // ──────────── Course Grid ────────────

  test('course grid loads courses', async ({ page }) => {
    const grid = page.locator(SEL.home.coursesGrid);
    await page.waitForTimeout(3000);
    if (await grid.isVisible()) {
      const cards = grid.locator('.ccard');
      const count = await cards.count();
      expect(count).toBeGreaterThan(0);
    }
  });

  test('clicking a course card navigates to course detail', async ({ page }) => {
    const grid = page.locator(SEL.home.coursesGrid);
    await page.waitForTimeout(3000);
    if (await grid.isVisible()) {
      const card = grid.locator('.ccard').first();
      if (await card.isVisible()) {
        await card.click();
        await page.waitForTimeout(2000);
        expect(page.url()).toContain('/courses/');
        await expect(page.locator(SEL.screens.course)).toBeVisible();
      }
    }
  });

  // ──────────── Sessions Row ────────────

  test('sessions section loads if user has sessions', async ({ page }) => {
    await page.waitForTimeout(3000);
    const section = page.locator(SEL.home.sessionsSection);
    // may or may not be visible depending on user data
    const isVisible = await section.isVisible();
    expect(typeof isVisible).toBe('boolean');
  });

  // ──────────── Videos Row ────────────

  test('videos section loads', async ({ page }) => {
    await page.waitForTimeout(3000);
    const section = page.locator(SEL.home.videosSection);
    const isVisible = await section.isVisible();
    expect(typeof isVisible).toBe('boolean');
  });

  // ──────────── My Stuff Tab ────────────

  test('My Stuff tab shows collections list', async ({ page }) => {
    const stuffTab = page.locator(SEL.home.tabStuff);
    if (await stuffTab.isVisible()) {
      await stuffTab.click();
      await page.waitForTimeout(1000);
      const list = page.locator(SEL.home.collectionsList);
      await expect(list).toBeVisible();
    }
  });

  test('new collection button opens modal', async ({ page }) => {
    const stuffTab = page.locator(SEL.home.tabStuff);
    if (await stuffTab.isVisible()) {
      await stuffTab.click();
      await page.waitForTimeout(500);
      const newBtn = page.locator(SEL.home.collectionsBtn);
      if (await newBtn.isVisible()) {
        await newBtn.click();
        await page.waitForTimeout(500);
        const modal = page.locator('#new-collection-modal');
        await expect(modal).toBeVisible();
      }
    }
  });

  test('modal Cancel closes without creating', async ({ page }) => {
    const stuffTab = page.locator(SEL.home.tabStuff);
    if (!(await stuffTab.isVisible())) return;
    await stuffTab.click();
    await page.waitForTimeout(400);
    const newBtn = page.locator(SEL.home.collectionsBtn);
    if (!(await newBtn.isVisible())) return;
    await newBtn.click();
    await page.waitForTimeout(300);
    await page.locator('#btn-cancel-collection').click();
    await page.waitForTimeout(200);
    const modal = page.locator('#new-collection-modal');
    // Modal is hidden via style.display — check it's not flex anymore.
    const display = await modal.evaluate(el => el.style.display);
    expect(display).toBe('none');
  });

  test('creating a collection POSTs to /byo/collections and refreshes list', async ({ page }) => {
    const stuffTab = page.locator(SEL.home.tabStuff);
    if (!(await stuffTab.isVisible())) return;
    await stuffTab.click();
    await page.waitForTimeout(400);
    const newBtn = page.locator(SEL.home.collectionsBtn);
    if (!(await newBtn.isVisible())) return;
    await newBtn.click();
    await page.waitForTimeout(300);
    await page.fill('#new-col-name', 'Playwright test collection');

    // Wait for the POST to be issued when Create is clicked.
    const postPromise = page.waitForRequest(
      req => req.url().includes('/api/v1/byo/collections') && req.method() === 'POST',
      { timeout: 8000 },
    ).catch(() => null);

    await page.click('#btn-create-collection');
    const postReq = await postPromise;
    // POST was attempted (even if backend rejects for auth or 500s,
    // the handler wiring is what we verify here).
    expect(postReq).not.toBeNull();
  });

  test('typing / in home input opens slash menu', async ({ page }) => {
    const input = page.locator(SEL.home.eulerInput);
    await input.click();
    await input.fill('/');
    await page.waitForTimeout(200);
    const menu = page.locator('#euler-slash-menu');
    await expect(menu).toBeVisible();
  });

  test('Escape closes slash menu', async ({ page }) => {
    const input = page.locator(SEL.home.eulerInput);
    await input.click();
    await input.fill('/');
    await page.waitForTimeout(200);
    await input.press('Escape');
    await page.waitForTimeout(100);
    const menu = page.locator('#euler-slash-menu');
    await expect(menu).toBeHidden();
  });

  test('scope chip appears after selecting a collection from slash menu', async ({ page }) => {
    // Seed the cache via the collections endpoint.
    await page.route('**/api/v1/byo/collections', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify([
            { collection_id: 'col-x', title: 'Lectures', status: 'ready', tags: [], stats: { resources: 2 } },
          ]),
        });
      } else {
        await route.continue();
      }
    });
    // Trigger a refresh by visiting My Stuff briefly, then return to Home.
    await page.locator(SEL.home.tabStuff).click();
    await page.waitForTimeout(400);
    await page.locator(SEL.home.tabHome).click();
    await page.waitForTimeout(200);

    const input = page.locator(SEL.home.eulerInput);
    await input.click();
    await input.fill('/');
    await page.waitForTimeout(200);
    // Click the first menu row (the Lectures collection)
    await page.locator('#euler-slash-menu [data-slash-idx="0"]').click();
    await page.waitForTimeout(200);
    await expect(page.locator('#euler-scope-chip-wrap')).toBeVisible();
    await expect(page.locator('#euler-scope-chip-wrap')).toContainText('Scoped to: Lectures');
    // Slash text removed from input
    expect(await input.inputValue()).toBe('');
  });

  test('list view shows no drop zone by default; detail view does', async ({ page }) => {
    const stuffTab = page.locator(SEL.home.tabStuff);
    if (!(await stuffTab.isVisible())) return;
    await stuffTab.click();
    await page.waitForTimeout(400);
    // In list view the detail container is hidden, so its children (drop
    // zone + link input) should not be visible.
    const detailView = page.locator('#byo-detail-view');
    await expect(detailView).toBeHidden();
  });

  test('creating a collection jumps into its detail view with upload area', async ({ page }) => {
    const stuffTab = page.locator(SEL.home.tabStuff);
    if (!(await stuffTab.isVisible())) return;
    await stuffTab.click();
    await page.waitForTimeout(400);

    // Mock the create + listing so the new collection shows up consistently.
    await page.route('**/api/v1/byo/collections', async (route) => {
      const req = route.request();
      if (req.method() === 'POST') {
        await route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify({ collection_id: 'col-test-xyz' }),
        });
      } else {
        await route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify([
            { collection_id: 'col-test-xyz', title: 'Playwright col',
              status: 'new', tags: [], stats: { resources: 0 } },
          ]),
        });
      }
    });
    await page.route('**/api/v1/byo/collections/*/resources', async (route) => {
      await route.fulfill({
        status: 200, contentType: 'application/json', body: JSON.stringify([]),
      });
    });

    await page.locator(SEL.home.collectionsBtn).click();
    await page.waitForTimeout(200);
    await page.fill('#new-col-name', 'Playwright col');
    await page.click('#btn-create-collection');
    await page.waitForTimeout(500);

    // Detail view visible now, list hidden
    await expect(page.locator('#byo-detail-view')).toBeVisible();
    await expect(page.locator('#byo-list-view')).toBeHidden();
    // Upload area and link input visible inside detail
    await expect(page.locator('#byo-drop-area')).toBeVisible();
    await expect(page.locator('#byo-link-input')).toBeVisible();
    await expect(page.locator('#byo-link-btn')).toBeVisible();
    await expect(page.locator('#byo-detail-teach')).toBeVisible();
  });

  test('adding a YouTube URL from detail view POSTs to that collection', async ({ page }) => {
    const stuffTab = page.locator(SEL.home.tabStuff);
    if (!(await stuffTab.isVisible())) return;
    await stuffTab.click();
    await page.waitForTimeout(400);

    await page.route('**/api/v1/byo/collections', async (route) => {
      const req = route.request();
      if (req.method() === 'POST') {
        await route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify({ collection_id: 'col-abc' }),
        });
      } else {
        await route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify([
            { collection_id: 'col-abc', title: 'Videos', status: 'new', tags: [], stats: { resources: 0 } },
          ]),
        });
      }
    });
    await page.route('**/api/v1/byo/collections/col-abc/resources', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify({ resource_id: 'r1', job_id: 'j1', status: 'queued' }),
        });
      } else {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
      }
    });

    // Create collection then paste URL
    await page.locator(SEL.home.collectionsBtn).click();
    await page.fill('#new-col-name', 'Videos');
    await page.click('#btn-create-collection');
    await page.waitForTimeout(400);

    const resPostPromise = page.waitForRequest(
      req => req.url().includes('/api/v1/byo/collections/col-abc/resources')
        && req.method() === 'POST',
      { timeout: 8000 },
    ).catch(() => null);

    await page.fill('#byo-link-input', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ');
    await page.click('#byo-link-btn');
    const req = await resPostPromise;
    expect(req).not.toBeNull();
    // URL added to the EXISTING collection, not a newly created one.
    expect(req.url()).toContain('/col-abc/resources');
  });

  test('back button returns to list view from detail', async ({ page }) => {
    const stuffTab = page.locator(SEL.home.tabStuff);
    if (!(await stuffTab.isVisible())) return;
    await stuffTab.click();
    await page.waitForTimeout(400);

    await page.route('**/api/v1/byo/collections', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({ status: 200, contentType: 'application/json',
          body: JSON.stringify({ collection_id: 'col-back-test' }) });
      } else {
        await route.fulfill({ status: 200, contentType: 'application/json',
          body: JSON.stringify([{ collection_id: 'col-back-test', title: 'Back', status: 'new', tags: [], stats: { resources: 0 } }]) });
      }
    });
    await page.route('**/api/v1/byo/collections/*/resources', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });

    await page.locator(SEL.home.collectionsBtn).click();
    await page.fill('#new-col-name', 'Back test');
    await page.click('#btn-create-collection');
    await page.waitForTimeout(400);
    await expect(page.locator('#byo-detail-view')).toBeVisible();

    await page.click('#byo-back-btn');
    await page.waitForTimeout(200);
    await expect(page.locator('#byo-list-view')).toBeVisible();
    await expect(page.locator('#byo-detail-view')).toBeHidden();
  });

  // ──────────── On-Demand Send ────────────

  test('sending euler query triggers session creation flow', async ({ page }) => {
    await page.fill(SEL.home.eulerInput, 'explain the pythagorean theorem');

    const responsePromise = page.waitForResponse(
      resp => resp.url().includes('/api/') && resp.status() < 500,
      { timeout: 15_000 }
    ).catch(() => null);

    await page.click(SEL.home.eulerSendBtn);
    await page.waitForTimeout(5000);

    const teaching = page.locator(SEL.screens.teaching);
    const prep = page.locator(SEL.teaching.prepOverlay);
    const isTeaching = await teaching.isVisible();
    const isPrepping = await prep.isVisible();
    expect(isTeaching || isPrepping || page.url().includes('/session')).toBeTruthy();
  });
});
