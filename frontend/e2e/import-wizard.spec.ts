import { test, expect } from '@playwright/test';
import { setupApiMocks, mockAuthentication } from './helpers/mock-api';
import * as path from 'path';

/**
 * E2E Test: Import Wizard
 * Tests the CSV import wizard flow with all 4 steps
 */
test.describe('Import Wizard', () => {
  test.beforeEach(async ({ page }) => {
    // Setup API mocks
    await setupApiMocks(page);
    await mockAuthentication(page);
    
    // Navigate to import page
    await page.goto('http://localhost:4200/vehicles/import');
    await page.waitForLoadState('networkidle');
  });

  test('should show all 4 steps in wizard', async ({ page }) => {
    // Check all steps are visible in the stepper
    await expect(page.locator('text=Upload fichier')).toBeVisible();
    await expect(page.locator('text=Configuration')).toBeVisible();
    await expect(page.locator('text=Mapping colonnes')).toBeVisible();
    await expect(page.locator('text=Résultat')).toBeVisible();
  });

  test('should upload CSV and navigate through all steps', async ({ page }) => {
    // Step 1: Upload file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(path.join(__dirname, 'fixtures/test-vehicles.csv'));
    
    // Wait for file to be recognized
    await expect(page.locator('button:has-text("Suivant")')).not.toBeDisabled();
    
    // Navigate to Step 2 (Configuration)
    await page.click('button:has-text("Suivant")');
    
    // Should be on Configuration step (step 2)
    await expect(page.locator('h3:has-text("Configuration de l\'import")')).toBeVisible();
    await expect(page.locator('input[type="number"]')).toBeVisible();
    
    // Check default skip lines is 6
    const skipInput = page.locator('input[type="number"]');
    await expect(skipInput).toHaveValue('6');
    
    // Verify preview section is visible
    await expect(page.locator('h4:has-text("Aperçu des données")')).toBeVisible();
    
    // Navigate to Step 3 (Mapping)
    await page.click('button:has-text("Suivant")');
    
    // Should be on Mapping step (step 3)
    await expect(page.locator('text=Colonne CSV')).toBeVisible();
    await expect(page.locator('text=Champ CLEF')).toBeVisible();
  });

  test('should have default skip lines = 6', async ({ page }) => {
    // Upload file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(path.join(__dirname, 'fixtures/test-vehicles.csv'));
    
    // Go to step 2
    await page.click('button:has-text("Suivant")');
    
    // Check default value
    const skipInput = page.locator('input[type="number"]');
    await expect(skipInput).toHaveValue('6');
  });

  test('should allow changing skip lines value', async ({ page }) => {
    // Upload file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(path.join(__dirname, 'fixtures/test-vehicles.csv'));
    
    // Go to step 2
    await page.click('button:has-text("Suivant")');
    
    // Change skip lines value
    const skipInput = page.locator('input[type="number"]');
    await skipInput.fill('3');
    
    // Verify the value changed
    await expect(skipInput).toHaveValue('3');
    
    // Verify hint text updates
    await expect(page.locator('text=Les lignes 1 à 3 seront ignorées')).toBeVisible();
  });

  test('should navigate back and forth between steps', async ({ page }) => {
    // Upload file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(path.join(__dirname, 'fixtures/test-vehicles.csv'));
    
    // Go to step 2
    await page.click('button:has-text("Suivant")');
    await expect(page.locator('h3:has-text("Configuration de l\'import")')).toBeVisible();
    
    // Go to step 3
    await page.click('button:has-text("Suivant")');
    await expect(page.locator('text=Colonne CSV')).toBeVisible();
    
    // Go back to step 2
    await page.click('button:has-text("Précédent")');
    await expect(page.locator('h3:has-text("Configuration de l\'import")')).toBeVisible();
    
    // Go back to step 1
    await page.click('button:has-text("Précédent")');
    await expect(page.locator('input[type="file"]')).toBeVisible();
  });

  test('should complete full import flow', async ({ page }) => {
    // Mock the import API endpoint
    await page.route('**/api/vehicles/import', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          created: 2,
          updated: 1,
          errors: [],
          warnings: []
        }),
      });
    });

    // Step 1: Upload file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(path.join(__dirname, 'fixtures/test-vehicles.csv'));
    await page.click('button:has-text("Suivant")');
    
    // Step 2: Configuration (keep default skip lines = 6)
    await page.click('button:has-text("Suivant")');
    
    // Step 3: Mapping (click import button)
    await page.click('button:has-text("Importer")');
    
    // Should show success message
    await expect(page.locator('.mat-mdc-snack-bar-container')).toContainText('Import terminé');
    
    // Should be on Step 4 (Result)
    await expect(page.locator('text=créés')).toBeVisible();
    await expect(page.locator('text=mis à jour')).toBeVisible();
  });

  test('should cancel import and return to vehicles list', async ({ page }) => {
    // Upload file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(path.join(__dirname, 'fixtures/test-vehicles.csv'));
    
    // Click cancel button
    await page.click('button:has-text("Annuler")');
    
    // Should navigate back to vehicles list
    await expect(page).toHaveURL(/.*vehicles$/);
  });
});

