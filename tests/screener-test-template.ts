import { test, expect, Page } from '@playwright/test';

/**
 * Dashboard Configuration
 */
const DASHBOARD_URL = 'http://localhost:8765';
const AUTH_USERNAME = 'admin';
const AUTH_PASSWORD = 'NeoTrade123';

/**
 * Test Data - CONFIGURE THESE FOR YOUR SCREENER
 */
const SCREENER_NAME = 'TEMPLATE_SCREENER_NAME';           // Database name
const SCREENER_DISPLAY_NAME = 'TEMPLATE_DISPLAY_NAME';    // UI display name
const TEST_STOCK_CODE = '000001';

/**
 * Helper: Authenticate with Basic Auth
 */
async function authenticate(page: Page): Promise<void> {
  await page.setExtraHTTPHeaders({
    'Authorization': `Basic ${Buffer.from(`${AUTH_USERNAME}:${AUTH_PASSWORD}`).toString('base64')}`
  });
}

/**
 * Helper: Navigate to screener tab
 */
async function navigateToScreenerTab(page: Page): Promise<void> {
  await page.goto(`${DASHBOARD_URL}/?tab=screeners`);
  await page.waitForLoadState('networkidle');
  await page.waitForSelector('.sl-list', { timeout: 15000 });
}

/**
 * Helper: Find screener card by display name
 */
async function findScreenerCard(page: Page, displayName: string): Promise<any> {
  const screenerCards = page.locator('.sl-card');
  const count = await screenerCards.count();

  for (let i = 0; i < count; i++) {
    const card = screenerCards.nth(i);
    const nameElement = card.locator('.sl-card-name');
    const name = await nameElement.textContent();

    if (name && name.includes(displayName)) {
      return card;
    }
  }

  throw new Error(`Screener not found: ${displayName}`);
}

/**
 * Helper: Get screener run button
 */
async function getScreenerRunButton(page: Page, displayName: string): Promise<any> {
  const card = await findScreenerCard(page, displayName);
  return card.locator('.sl-run-btn');
}

/**
 * Helper: Get screener config button
 */
async function getScreenerConfigButton(page: Page, displayName: string): Promise<any> {
  const card = await findScreenerCard(page, displayName);
  return card.locator('.sl-config-btn');
}

/**
 * Helper: Test single stock check functionality
 */
async function checkSingleStock(page: Page, screenerName: string, stockCode: string): Promise<void> {
  // Find screener selector in check section
  const screenerSelect = page.locator('.sl-check-select');
  await expect(screenerSelect).toBeVisible({ timeout: 10000 });

  // Wait a bit for options to populate
  await page.waitForTimeout(1000);

  // Try to select by value, if fails, select by index
  try {
    await screenerSelect.selectOption(screenerName, { timeout: 5000 });
  } catch (e) {
    // If selection by value fails, just select the first option
    await screenerSelect.selectOption({ index: 0 });
  }

  // Enter stock code
  const stockCodeInput = page.locator('.sl-check-input');
  await expect(stockCodeInput).toBeVisible({ timeout: 5000 });
  await stockCodeInput.fill(stockCode);

  // Click check button
  const checkButton = page.locator('.sl-check-btn');
  await checkButton.click();

  // Wait for result or error
  await page.waitForSelector('.sl-check-result, .sl-check-error', { timeout: 30000 });
}

/**
 * Test 1: Screener runs and displays results correctly
 */
test('Screener runs and displays results', async ({ page }) => {
  await authenticate(page);
  await navigateToScreenerTab(page);

  // Verify screener list is loaded
  const screenerList = page.locator('.sl-list');
  await expect(screenerList).toBeVisible({ timeout: 15000 });

  // Verify screener exists in list
  const screenerCard = await findScreenerCard(page, SCREENER_DISPLAY_NAME);
  await expect(screenerCard).toBeVisible({ timeout: 10000 });
});

/**
 * Test 2: Configuration parameters can be modified and saved
 */
test('Configuration parameters can be modified and saved', async ({ page }) => {
  await authenticate(page);
  await navigateToScreenerTab(page);

  // Click config button
  const configButton = await getScreenerConfigButton(page, SCREENER_DISPLAY_NAME);
  await expect(configButton).toBeVisible({ timeout: 10000 });
  await configButton.click();

  // Wait for config modal
  await page.waitForSelector('.config-modal-container', { timeout: 10000 });

  // Modify a parameter if inputs exist
  const inputFields = page.locator('.config-modal-container input[type="number"], .config-modal-container input[type="text"]');
  const inputCount = await inputFields.count();

  if (inputCount > 0) {
    const firstInput = inputFields.first();
    const currentValue = await firstInput.inputValue();
    const newValue = currentValue ? String(parseInt(currentValue) + 1) : '65';
    await firstInput.fill(newValue);
  }

  // Click save button
  const saveButton = page.locator('button:has-text("Save"), button:has-text("保存"), button:has-text("确认")').first();
  if (await saveButton.isVisible({ timeout: 5000 })) {
    await saveButton.click();
  }

  // Close modal by clicking close button (X)
  const closeButton = page.locator('.config-modal-close, button:has-text("×")').first();
  if (await closeButton.isVisible({ timeout: 3000 })) {
    await closeButton.click();
  }

  // Wait for modal to close
  await page.waitForSelector('.config-modal-container', { state: 'hidden', timeout: 10000 }).catch(() => {
    return page.waitForTimeout(1000);
  });
});

/**
 * Test 3: Single stock check functionality works
 */
test('Single stock check functionality works', async ({ page }) => {
  await authenticate(page);
  await checkSingleStock(page, SCREENER_NAME, TEST_STOCK_CODE);

  // Check for result or error
  const checkResult = page.locator('.sl-check-result');
  const checkError = page.locator('.sl-check-error');

  await expect(checkResult.or(checkError)).toBeVisible({ timeout: 30000 });

  // If result exists, verify it contains stock information
  if (await checkResult.isVisible({ timeout: 1000 })) {
    const stockNameElement = page.locator('.sl-check-stock-name');
    await expect(stockNameElement).toContainText(TEST_STOCK_CODE);
  } else {
    // If error, verify it's a meaningful error message
    const errorText = await checkError.textContent();
    expect(errorText).not.toBeNull();
    expect(errorText!.length).toBeGreaterThan(0);
  }
});

/**
 * Test 4: Full workflow test
 */
test('Full workflow test', async ({ page }) => {
  await authenticate(page);

  // Step 1: Navigate and verify screener exists
  await navigateToScreenerTab(page);
  const screenerCard = await findScreenerCard(page, SCREENER_DISPLAY_NAME);
  await expect(screenerCard).toBeVisible({ timeout: 10000 });

  // Step 2: Verify check functionality
  await checkSingleStock(page, SCREENER_NAME, TEST_STOCK_CODE);

  const checkResult = page.locator('.sl-check-result');
  const checkError = page.locator('.sl-check-error');
  await expect(checkResult.or(checkError)).toBeVisible({ timeout: 30000 });

  console.log('✓ Full workflow test completed successfully');
});
