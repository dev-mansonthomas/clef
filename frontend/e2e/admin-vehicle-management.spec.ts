import { test, expect } from '@playwright/test';
import { setupApiMocks, mockAuthentication } from './helpers/mock-api';

/**
 * E2E Test: Admin - Vehicle Management Flow
 * Tests: Login → Vehicle List → Edit Vehicle
 */
test.describe('Admin - Vehicle Management', () => {
  test.beforeEach(async ({ page }) => {
    // Setup API mocks
    await setupApiMocks(page);
    await mockAuthentication(page);
  });

  test('should navigate from login to vehicle list and edit a vehicle', async ({ page }) => {
    // Navigate to admin app
    await page.goto('http://localhost:4200');

    // Should redirect to dashboard after authentication
    await expect(page).toHaveURL(/.*dashboard/);
    await expect(page.locator('h1')).toContainText('Tableau de bord');

    // Navigate to vehicles list
    await page.click('a[routerlink="/vehicles"]');
    await expect(page).toHaveURL(/.*vehicles$/);

    // Wait for vehicles to load
    await page.waitForSelector('table');

    // Verify vehicle list is displayed
    await expect(page.locator('table')).toBeVisible();
    
    // Check that mock vehicles are displayed
    await expect(page.locator('text=VL75-01')).toBeVisible();
    await expect(page.locator('text=VL75-02')).toBeVisible();
    await expect(page.locator('text=Renault')).toBeVisible();
    await expect(page.locator('text=Peugeot')).toBeVisible();

    // Click on first vehicle row to edit
    await page.click('table tbody tr:first-child');

    // Should navigate to edit page
    await expect(page).toHaveURL(/.*vehicles\/.*\/edit/);
    await expect(page.locator('h2')).toContainText('Édition du véhicule');

    // Verify form is populated with vehicle data
    await expect(page.locator('input[formcontrolname="immat"]')).toHaveValue('AB-123-CD');
    await expect(page.locator('input[formcontrolname="indicatif"]')).toHaveValue('VL75-01');
    await expect(page.locator('input[formcontrolname="marque"]')).toHaveValue('Renault');
    await expect(page.locator('input[formcontrolname="modele"]')).toHaveValue('Kangoo');

    // Update a field (commentaires - editable field)
    await page.fill('textarea[formcontrolname="commentaires"]', 'Véhicule de liaison - Mis à jour');

    // Mock the update API call
    await page.route('**/api/vehicles/VL75-01-KANGOO', async (route) => {
      if (route.request().method() === 'PATCH') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ message: 'Vehicle updated successfully' }),
        });
      } else {
        await route.continue();
      }
    });

    // Submit the form
    await page.click('button[type="submit"]');

    // Should show success message
    await expect(page.locator('.mat-mdc-snack-bar-container')).toContainText('mis à jour avec succès');

    // Should navigate back to vehicle list
    await expect(page).toHaveURL(/.*vehicles$/);
  });

  test('should filter vehicles by availability', async ({ page }) => {
    await page.goto('http://localhost:4200/vehicles');

    // Wait for vehicles to load
    await page.waitForSelector('table');

    // Initially, all vehicles should be visible
    const allRows = await page.locator('table tbody tr').count();
    expect(allRows).toBeGreaterThan(0);

    // Filter by availability (if filter exists)
    const filterSelect = page.locator('mat-select[formcontrolname="availabilityFilter"]');
    if (await filterSelect.isVisible()) {
      await filterSelect.click();
      await page.click('mat-option:has-text("Disponible")');

      // Verify filtered results
      await expect(page.locator('table tbody tr')).toHaveCount(2); // Both mock vehicles are available
    }
  });

  test('should search vehicles by text', async ({ page }) => {
    await page.goto('http://localhost:4200/vehicles');

    // Wait for vehicles to load
    await page.waitForSelector('table');

    // Search for specific vehicle
    const searchInput = page.locator('input[placeholder*="Rechercher"]');
    if (await searchInput.isVisible()) {
      await searchInput.fill('VL75-01');

      // Should show only matching vehicle
      await expect(page.locator('text=VL75-01')).toBeVisible();
      await expect(page.locator('text=VL75-02')).not.toBeVisible();
    }
  });

  test('should display vehicle status colors correctly', async ({ page }) => {
    await page.goto('http://localhost:4200/vehicles');

    // Wait for vehicles to load
    await page.waitForSelector('table');

    // Check status indicators
    // VL75-01 should have green status (CT valid)
    const firstRow = page.locator('table tbody tr:first-child');
    await expect(firstRow.locator('.status-green')).toBeVisible();

    // VL75-02 should have orange status (CT < 2 months)
    const secondRow = page.locator('table tbody tr:nth-child(2)');
    await expect(secondRow.locator('.status-orange')).toBeVisible();
  });
});

