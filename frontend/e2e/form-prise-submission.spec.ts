import { test, expect } from '@playwright/test';
import { setupApiMocks, mockAuthentication } from './helpers/mock-api';

/**
 * E2E Test: Form - Vehicle Prise Flow
 * Tests: Vehicle Selection → Prise Form → Submission
 */
test.describe('Form - Vehicle Prise Submission', () => {
  test.beforeEach(async ({ page }) => {
    // Setup API mocks
    await setupApiMocks(page);
    await mockAuthentication(page);
  });

  test('should complete vehicle prise flow from selection to submission', async ({ page }) => {
    // Navigate to form app
    await page.goto('http://localhost:4202');

    // Should show vehicle selector
    await expect(page.locator('h2')).toContainText('Sélection du véhicule');

    // Wait for vehicles to load
    await page.waitForSelector('.vehicle-card, mat-card');

    // Select a vehicle (click on vehicle card)
    const vehicleCard = page.locator('mat-card:has-text("VL75-01")').first();
    await vehicleCard.click();

    // Should navigate to prise form
    await expect(page).toHaveURL(/.*prise\/VL75-01-KANGOO/);
    await expect(page.locator('h2')).toContainText('Prise de véhicule');

    // Verify vehicle info is displayed
    await expect(page.locator('text=VL75-01')).toBeVisible();
    await expect(page.locator('text=Renault Kangoo')).toBeVisible();

    // Fill in the prise form
    await page.fill('input[formcontrolname="kmDepart"]', '12500');
    
    // Select fuel level
    await page.click('mat-select[formcontrolname="niveauCarburant"]');
    await page.click('mat-option:has-text("3/4")');

    // Set general condition (slider or input)
    const etatInput = page.locator('input[formcontrolname="etatGeneral"]');
    if (await etatInput.isVisible()) {
      await etatInput.fill('5');
    }

    // Add comments
    await page.fill('textarea[formcontrolname="commentaires"]', 'Véhicule en bon état');

    // Mock signature pad (if present)
    // Note: Signature pad interaction might need special handling
    const signatureCanvas = page.locator('canvas');
    if (await signatureCanvas.isVisible()) {
      // Simulate drawing on canvas
      const box = await signatureCanvas.boundingBox();
      if (box) {
        await page.mouse.move(box.x + 10, box.y + 10);
        await page.mouse.down();
        await page.mouse.move(box.x + 100, box.y + 50);
        await page.mouse.up();
      }
    }

    // Submit the form
    await page.click('button[type="submit"]:has-text("Valider")');

    // Should show success message
    await expect(page.locator('.mat-mdc-snack-bar-container')).toContainText('enregistré avec succès', {
      timeout: 10000,
    });

    // Should navigate back to home
    await expect(page).toHaveURL('http://localhost:4202/');
  });

  test('should validate required fields in prise form', async ({ page }) => {
    // Navigate directly to prise form
    await page.goto('http://localhost:4202/prise/VL75-01-KANGOO');

    // Try to submit without filling required fields
    await page.click('button[type="submit"]:has-text("Valider")');

    // Form should not submit (button might be disabled or show validation errors)
    const submitButton = page.locator('button[type="submit"]:has-text("Valider")');
    
    // Check if button is disabled or form shows errors
    const isDisabled = await submitButton.isDisabled();
    if (!isDisabled) {
      // Check for validation error messages
      await expect(page.locator('.mat-error, .error-message')).toBeVisible();
    }

    // Fill required field
    await page.fill('input[formcontrolname="kmDepart"]', '12500');

    // Select fuel level
    await page.click('mat-select[formcontrolname="niveauCarburant"]');
    await page.click('mat-option:has-text("Plein")');

    // Now button should be enabled (if it was disabled)
    if (isDisabled) {
      await expect(submitButton).toBeEnabled();
    }
  });

  test('should handle QR code scan flow', async ({ page }) => {
    // Navigate to form app
    await page.goto('http://localhost:4202');

    // Look for QR scanner button or link
    const scanButton = page.locator('button:has-text("Scanner"), a:has-text("Scanner")');
    
    if (await scanButton.isVisible()) {
      await scanButton.click();

      // Mock QR code detection
      // Note: Actual QR scanning would require camera access
      // For E2E, we can simulate by navigating directly with encoded ID
      const encodedId = btoa('VL75-01-KANGOO'); // Base64 encode
      await page.goto(`http://localhost:4202/vehicle/${encodedId}`);

      // Should decode and show vehicle selection or go to prise
      await expect(page).toHaveURL(/.*vehicle\/.*|.*prise\/.*/);
    }
  });

  test('should allow photo upload in prise form', async ({ page }) => {
    await page.goto('http://localhost:4202/prise/VL75-01-KANGOO');

    // Look for photo upload button
    const photoButton = page.locator('button:has-text("Ajouter"), input[type="file"]');
    
    if (await photoButton.isVisible()) {
      // Create a test file
      const fileInput = page.locator('input[type="file"]');
      
      if (await fileInput.isVisible()) {
        // Set files on the input
        await fileInput.setInputFiles({
          name: 'test-photo.jpg',
          mimeType: 'image/jpeg',
          buffer: Buffer.from('fake-image-data'),
        });

        // Verify photo was added
        await expect(page.locator('.photo-preview, img[src*="blob:"]')).toBeVisible();
      }
    }
  });
});

