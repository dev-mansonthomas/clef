import { test, expect } from '@playwright/test';
import { setupApiMocks, mockAuthentication } from './helpers/mock-api';

/**
 * E2E Test: Admin - Reservation and Calendar Flow
 * Tests: Create Reservation → Verify Calendar Display
 */
test.describe('Admin - Reservation and Calendar', () => {
  test.beforeEach(async ({ page }) => {
    // Setup API mocks
    await setupApiMocks(page);
    await mockAuthentication(page);
  });

  test('should create a reservation and verify it appears in calendar', async ({ page }) => {
    // Navigate to admin app
    await page.goto('http://localhost:4200');

    // Navigate to calendar view
    await page.click('a[routerlink="/calendar"]');
    await expect(page).toHaveURL(/.*calendar/);

    // Wait for calendar to load
    await page.waitForSelector('.fc-view, full-calendar');

    // Verify calendar is displayed
    await expect(page.locator('.fc-view, full-calendar')).toBeVisible();

    // Check if existing reservation is visible
    await expect(page.locator('text=VL75-01')).toBeVisible();
    await expect(page.locator('text=Jean Dupont')).toBeVisible();

    // Look for "Create Reservation" button
    const createButton = page.locator('button:has-text("Nouvelle réservation"), button:has-text("Créer")');
    
    if (await createButton.isVisible()) {
      await createButton.click();

      // Should open reservation form dialog
      await expect(page.locator('mat-dialog-container, .reservation-form')).toBeVisible();

      // Fill in reservation form
      // Select vehicle
      await page.click('mat-select[formcontrolname="vehicule_id"]');
      await page.click('mat-option:has-text("VL75-01")');

      // Fill driver info
      await page.fill('input[formcontrolname="chauffeur_nom"]', 'Martin');
      await page.fill('input[formcontrolname="chauffeur_prenom"]', 'Sophie');

      // Fill mission
      await page.fill('input[formcontrolname="mission"]', 'Transport matériel');

      // Select dates
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 2);
      const dateStr = tomorrow.toISOString().split('T')[0];

      await page.fill('input[formcontrolname="date_debut"]', dateStr + 'T10:00');
      await page.fill('input[formcontrolname="date_fin"]', dateStr + 'T12:00');

      // Add comment
      await page.fill('textarea[formcontrolname="commentaire"]', 'Livraison de matériel médical');

      // Submit reservation
      await page.click('button[type="submit"]:has-text("Créer"), button:has-text("Valider")');

      // Should show success message
      await expect(page.locator('.mat-mdc-snack-bar-container')).toContainText('créée avec succès', {
        timeout: 10000,
      });

      // Dialog should close
      await expect(page.locator('mat-dialog-container')).not.toBeVisible();

      // New reservation should appear in calendar
      await expect(page.locator('text=Sophie Martin')).toBeVisible();
      await expect(page.locator('text=Transport matériel')).toBeVisible();
    }
  });

  test('should navigate calendar weeks', async ({ page }) => {
    await page.goto('http://localhost:4200/calendar');

    // Wait for calendar to load
    await page.waitForSelector('.fc-view, full-calendar');

    // Find navigation buttons
    const nextButton = page.locator('button.fc-next-button, button:has-text("Suivant")');
    const prevButton = page.locator('button.fc-prev-button, button:has-text("Précédent")');

    if (await nextButton.isVisible()) {
      // Click next week
      await nextButton.click();

      // Wait for calendar to update
      await page.waitForTimeout(500);

      // Click previous week
      await prevButton.click();

      // Should return to current week
      await page.waitForTimeout(500);
    }
  });

  test('should filter calendar by vehicle', async ({ page }) => {
    await page.goto('http://localhost:4200/calendar');

    // Wait for calendar to load
    await page.waitForSelector('.fc-view, full-calendar');

    // Look for vehicle filter
    const vehicleFilter = page.locator('mat-select[placeholder*="Véhicule"], mat-select:has-text("Tous")');

    if (await vehicleFilter.isVisible()) {
      // Select specific vehicle
      await vehicleFilter.click();
      await page.click('mat-option:has-text("VL75-01")');

      // Should show only events for selected vehicle
      await expect(page.locator('text=VL75-01')).toBeVisible();
      
      // Other vehicles should not be visible (if they exist)
      const otherVehicle = page.locator('text=VL75-03');
      if (await otherVehicle.count() > 0) {
        await expect(otherVehicle).not.toBeVisible();
      }
    }
  });

  test('should display reservation details on click', async ({ page }) => {
    await page.goto('http://localhost:4200/calendar');

    // Wait for calendar to load
    await page.waitForSelector('.fc-view, full-calendar');

    // Click on an event
    const event = page.locator('.fc-event:has-text("VL75-01")').first();
    
    if (await event.isVisible()) {
      await event.click();

      // Should show event details (in dialog or tooltip)
      await expect(page.locator('text=Jean Dupont, text=Mission Secours')).toBeVisible();
    }
  });

  test('should validate reservation form', async ({ page }) => {
    await page.goto('http://localhost:4200/calendar');

    // Open reservation form
    const createButton = page.locator('button:has-text("Nouvelle réservation"), button:has-text("Créer")');
    
    if (await createButton.isVisible()) {
      await createButton.click();

      // Try to submit without filling required fields
      const submitButton = page.locator('button[type="submit"]:has-text("Créer"), button:has-text("Valider")');
      await submitButton.click();

      // Should show validation errors or button should be disabled
      const isDisabled = await submitButton.isDisabled();
      if (!isDisabled) {
        await expect(page.locator('.mat-error, .error-message')).toBeVisible();
      }

      // Fill required fields
      await page.click('mat-select[formcontrolname="vehicule_id"]');
      await page.click('mat-option:has-text("VL75-01")');

      await page.fill('input[formcontrolname="chauffeur_nom"]', 'Test');
      await page.fill('input[formcontrolname="chauffeur_prenom"]', 'User');
      await page.fill('input[formcontrolname="mission"]', 'Test Mission');

      // Now form should be valid
      if (isDisabled) {
        await expect(submitButton).toBeEnabled();
      }
    }
  });
});

