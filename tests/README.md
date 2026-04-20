# Playwright Automated Tests

This directory contains automated tests for the NeoTrade2 Dashboard using Playwright.

## Quick Start

### 1. Install Dependencies (First Time Only)

```bash
npm install -D @playwright/test
npx playwright install chromium
```

### 2. Run Tests

Run all tests:
```bash
npx playwright test
```

Run tests in UI mode (with browser preview):
```bash
npx playwright test --ui
```

Run tests with debug mode (step through tests):
```bash
npx playwright test --debug
```

Run specific test:
```bash
npx playwright test screener-test.spec.ts
```

### 3. View Test Reports

After running tests:
```bash
npx playwright show-report
```

## Test Coverage

### Screener Test Suite (`screener-test.spec.ts`)

Tests the three critical functions of every screener:

1. **Screener Runs and Displays Results**
   - Navigates to screener page
   - Runs screener with current date
   - Verifies results are displayed or "no results" message appears
   - Validates result structure if results exist

2. **Configuration Parameters Can Be Modified and Saved**
   - Opens configuration modal
   - Modifies test parameters (e.g., min_weeks, volume_contraction_threshold)
   - Saves configuration
   - Reopens config to verify persistence
   - Confirms save success message

3. **Single Stock Check Functionality Works**
   - Navigates to single stock check tab
   - Enters test stock code (000001)
   - Runs check
   - Verifies result or error is displayed
   - Validates output contains stock information

4. **Full Workflow Test**
   - Runs complete workflow: Run → Config → Check
   - Verifies all steps complete successfully

## Configuration

Update test configuration in `screener-test.spec.ts`:

```typescript
const DASHBOARD_URL = 'http://localhost:8765';
const AUTH_USERNAME = 'admin';
const AUTH_PASSWORD = 'NeoTrade123'; // Update this!

const SCREENER_NAME = 'lao_ya_tou_zhou_xian_screener';
const TEST_STOCK_CODE = '000001';
```

## Test Requirements

1. **Flask Dashboard Running**: Ensure Flask backend is running on port 8765
   ```bash
   launchctl list | grep flask
   ```

2. **Authentication**: Update `AUTH_PASSWORD` to match your actual dashboard password

3. **Test Data**: Update `TEST_STOCK_CODE` to use a stock that exists in your database

## Adding New Screener Tests

To add tests for a new screener:

1. **Create new test file**:
   ```bash
   touch tests/new-screener-test.spec.ts
   ```

2. **Copy existing test** and update configuration:
   ```typescript
   const SCREENER_NAME = 'your_screener_name';
   const SCREENER_DISPLAY_NAME = 'Your Screener Display Name';
   ```

3. **Customize test logic** if needed (e.g., specific config parameters)

## Debugging Failed Tests

### View Screenshots
Failed tests automatically save screenshots to:
```
test-results/
  ├── your-test-name/
  │   ├── screenshot-1.png
  │   └── screenshot-2.png
```

### View Traces
Failed tests save execution traces:
```bash
npx playwright show-trace test-results/your-test-name/trace.zip
```

### View Videos
Videos are saved for failed tests:
```
test-results/your-test-name/video.webm
```

## Common Issues

### "Page not found" or 404 errors
- Verify Flask dashboard is running: `curl http://localhost:8765`
- Check port is correct (default: 8765)

### Authentication failures
- Verify username and password in test config
- Check backend logs: `tail -f /Users/mac/NeoTrade2/logs/flask.stdout.log`

### Tests timeout
- Increase timeout in test: `test('test name', { timeout: 120000 }, async ({ page }) => {`
- Check if API calls are slow or failing

### "Element not found" errors
- Update test selectors to match actual HTML structure
- Use Playwright inspector to find correct selectors:
  ```bash
  npx playwright codegen http://localhost:8765
  ```

## Continuous Integration

To run tests in CI/CD:

```yaml
# .github/workflows/test.yml
- name: Install dependencies
  run: npm ci

- name: Install Playwright browsers
  run: npx playwright install --with-deps chromium

- name: Run Playwright tests
  run: npx playwright test

- name: Upload test results
  if: always()
  uses: actions/upload-artifact@v3
  with:
    name: playwright-report
    path: playwright-report/
```

## Best Practices

1. **Use descriptive test names**: "Screener runs and displays results" vs "Test 1"

2. **Use page fixtures**: Test isolation, automatic cleanup

3. **Wait for network idle**: `await page.waitForLoadState('networkidle')`

4. **Use specific selectors**: `data-testid="save-config"` vs `.save-btn`

5. **Add custom data attributes** to HTML elements for reliable test selection:
   ```html
   <button data-testid="run-screener">Run</button>
   ```

## Resources

- [Playwright Documentation](https://playwright.dev)
- [Playwright Best Practices](https://playwright.dev/docs/best-practices)
- [Test Generator](https://playwright.dev/docs/codegen)
- [Trace Viewer](https://playwright.dev/docs/trace-viewer)

---

**Last Updated**: 2026-04-16
**Maintainer**: Claude Code
