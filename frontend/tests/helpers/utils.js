/**
 * Shared test utilities: waits, assertions, API mocking, network helpers.
 */

/**
 * Wait for a screen to become the visible active screen.
 */
async function waitForScreen(page, screenSelector, timeout = 10_000) {
  await page.waitForSelector(screenSelector, { state: 'visible', timeout });
}

/**
 * Assert that exactly one screen is visible at a time.
 */
async function assertOneScreenVisible(page, expectedId) {
  const screens = ['#landing-screen', '#business-screen', '#login-panel',
                   '#browse-screen', '#course-screen', '#ondemand-screen'];
  for (const sel of screens) {
    const el = page.locator(sel);
    if (sel === expectedId) {
      await expect(el).toBeVisible();
    }
  }
}

/**
 * Wait for network idle (no pending requests for the given ms).
 */
async function waitForNetworkIdle(page, ms = 500) {
  await page.waitForLoadState('networkidle');
}

/**
 * Mock a GET API endpoint with a fixed JSON response.
 */
async function mockGetAPI(page, urlPattern, responseBody, status = 200) {
  await page.route(urlPattern, route => {
    route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify(responseBody),
    });
  });
}

/**
 * Mock a POST API endpoint.
 */
async function mockPostAPI(page, urlPattern, responseBody, status = 200) {
  await page.route(urlPattern, route => {
    if (route.request().method() === 'POST') {
      route.fulfill({
        status,
        contentType: 'application/json',
        body: JSON.stringify(responseBody),
      });
    } else {
      route.continue();
    }
  });
}

/**
 * Mock the SSE /api/chat endpoint with a scripted response.
 * Pass an array of SSE lines: ["data: {...}", "data: {...}"]
 */
async function mockChatSSE(page, sseLines) {
  await page.route('**/api/chat', route => {
    const body = sseLines.join('\n') + '\n\ndata: [DONE]\n\n';
    route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body,
    });
  });
}

/**
 * Collect all network requests matching a pattern during an action.
 */
async function collectRequests(page, urlPattern, action) {
  const requests = [];
  const handler = req => {
    if (req.url().match(urlPattern)) requests.push(req);
  };
  page.on('request', handler);
  await action();
  page.removeListener('request', handler);
  return requests;
}

/**
 * Wait for a specific API response.
 */
async function waitForAPI(page, urlPattern, timeout = 15_000) {
  return page.waitForResponse(
    resp => resp.url().match(urlPattern) && resp.status() === 200,
    { timeout }
  );
}

/**
 * Take a named screenshot for visual reference.
 */
async function screenshot(page, name) {
  await page.screenshot({ path: `test-results/screenshots/${name}.png`, fullPage: true });
}

export {
  waitForScreen,
  assertOneScreenVisible,
  waitForNetworkIdle,
  mockGetAPI,
  mockPostAPI,
  mockChatSSE,
  collectRequests,
  waitForAPI,
  screenshot,
};
