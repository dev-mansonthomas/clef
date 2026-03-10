# E2E Tests - CLEF

End-to-end tests for the CLEF application using Playwright.

## Overview

These tests cover critical user flows across both admin and form applications:

1. **Admin - Vehicle Management** (`admin-vehicle-management.spec.ts`)
   - Login → Vehicle List → Edit Vehicle
   - Vehicle filtering and search
   - Status color display

2. **Form - Vehicle Prise** (`form-prise-submission.spec.ts`)
   - Vehicle Selection → Prise Form → Submission
   - Form validation
   - QR code scanning flow
   - Photo upload

3. **Admin - Reservations** (`admin-reservation-calendar.spec.ts`)
   - Create Reservation → Verify Calendar
   - Calendar navigation
   - Vehicle filtering
   - Reservation details

## Running Tests

### Prerequisites

```bash
cd frontend
npm install
```

### Run all tests

```bash
npm run e2e
```

### Run tests in UI mode (interactive)

```bash
npm run e2e:ui
```

### Run tests in headed mode (see browser)

```bash
npm run e2e:headed
```

### Run specific test file

```bash
npx playwright test admin-vehicle-management.spec.ts
```

### Run tests in debug mode

```bash
npx playwright test --debug
```

## Test Architecture

### Mock API

All tests run against mocked backend APIs (no real API calls):

- **Mock Data**: `e2e/fixtures/mock-data.ts`
  - Mock vehicles, users, reservations
  - Matches backend mock data structure

- **Mock API Helpers**: `e2e/helpers/mock-api.ts`
  - `setupApiMocks(page)`: Intercepts all API calls
  - `mockAuthentication(page)`: Sets up auth state

### Test Structure

Each test file follows this pattern:

```typescript
test.describe('Feature Name', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
    await mockAuthentication(page);
  });

  test('should do something', async ({ page }) => {
    // Test implementation
  });
});
```

## Configuration

Configuration is in `playwright.config.ts`:

- **Base URLs**:
  - Admin app: `http://localhost:4200`
  - Form app: `http://localhost:4202`

- **Web Servers**: Automatically starts both apps before tests
  - `npm run start:admin` (port 4200)
  - `npm run start:form` (port 4202)

- **Browsers**: Chromium (can be extended to Firefox, WebKit)

- **Reporters**: HTML report (opens automatically on failure)

## CI Integration

Tests are configured for CI/CD:

- Retries: 2 retries on CI
- Workers: 1 worker on CI (sequential)
- Screenshots: Captured on failure
- Traces: Captured on first retry

### GitHub Actions Example

```yaml
- name: Install dependencies
  run: cd frontend && npm ci

- name: Install Playwright browsers
  run: cd frontend && npx playwright install --with-deps

- name: Run E2E tests
  run: cd frontend && npm run e2e

- name: Upload test results
  if: always()
  uses: actions/upload-artifact@v3
  with:
    name: playwright-report
    path: frontend/playwright-report/
```

## Debugging

### View test report

```bash
npx playwright show-report
```

### Generate trace

```bash
npx playwright test --trace on
```

### View trace

```bash
npx playwright show-trace trace.zip
```

## Adding New Tests

1. Create a new spec file in `e2e/`
2. Import helpers: `import { setupApiMocks, mockAuthentication } from './helpers/mock-api'`
3. Add mock data if needed in `e2e/fixtures/mock-data.ts`
4. Follow existing test patterns
5. Run tests to verify

## Best Practices

- ✅ Use data-testid attributes for stable selectors
- ✅ Mock all API calls (no real backend)
- ✅ Test user flows, not implementation details
- ✅ Keep tests independent and isolated
- ✅ Use meaningful test descriptions
- ✅ Clean up after tests (automatic with beforeEach)

## Troubleshooting

### Tests fail with "Timeout"

- Increase timeout in test: `test('...', async ({ page }) => { ... }, { timeout: 60000 })`
- Check if apps are running on correct ports
- Verify mock API responses

### Tests fail with "Element not found"

- Check selector (use Playwright Inspector: `npx playwright test --debug`)
- Verify element is visible: `await expect(element).toBeVisible()`
- Add wait: `await page.waitForSelector('selector')`

### Apps don't start

- Check ports 4200 and 4202 are available
- Manually start apps: `npm run start:admin` and `npm run start:form`
- Set `reuseExistingServer: true` in config

