import { test, expect } from '@playwright/test';
import { setupApiMocks, mockAuthentication } from './helpers/mock-api';
import { vehiclesCsvFile } from './helpers/vehicles-csv';
import type { Page } from '@playwright/test';

/**
 * Le stepper Material conserve dans le DOM les boutons de toutes les étapes ;
 * un seul jeu est visible à la fois. Ces helpers ciblent celui de l'étape
 * courante — sans quoi le mode strict de Playwright échoue sur 2 correspondances,
 * ou clique sur un bouton masqué et attend jusqu'au timeout.
 */
const nextButton = (page: Page) =>
  page.locator('button:has-text("Suivant"):visible').first();

const previousButton = (page: Page) =>
  page.locator('button:has-text("Précédent"):visible').first();

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
    // Les libellés du stepper, et eux seuls : « Configuration » tout court
    // apparaît aussi dans la navigation latérale et dans le panneau d'aide, ce
    // qui faisait échouer l'assertion en mode strict.
    const stepLabels = page.locator('.mat-step-text-label');
    await expect(stepLabels.filter({ hasText: 'Upload fichier' })).toBeVisible();
    await expect(stepLabels.filter({ hasText: /^Configuration$/ })).toBeVisible();
    await expect(stepLabels.filter({ hasText: 'Mapping colonnes' })).toBeVisible();
    await expect(stepLabels.filter({ hasText: 'Résultat' })).toBeVisible();
  });

  test('should upload CSV and navigate through all steps', async ({ page }) => {
    // Step 1: Upload file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(vehiclesCsvFile());
    
    // Wait for file to be recognized
    await expect(nextButton(page)).not.toBeDisabled();
    
    // Navigate to Step 2 (Configuration)
    await nextButton(page).click();
    
    // Should be on Configuration step (step 2)
    await expect(page.locator('h3:has-text("Configuration de l\'import")')).toBeVisible();
    await expect(page.locator('input[type="number"]')).toBeVisible();
    
    // Check default skip lines is 6
    const skipInput = page.locator('input[type="number"]');
    await expect(skipInput).toHaveValue('6');
    
    // Verify preview section is visible
    await expect(page.locator('h4:has-text("Aperçu des données")')).toBeVisible();
    
    // Navigate to Step 3 (Mapping)
    await nextButton(page).click();
    
    // Should be on Mapping step (step 3)
    await expect(page.locator('text=Colonne CSV')).toBeVisible();
    await expect(page.getByText('Champ CLEF', { exact: true })).toBeVisible();
  });

  test('should have default skip lines = 6', async ({ page }) => {
    // Upload file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(vehiclesCsvFile());
    
    // Go to step 2
    await nextButton(page).click();
    
    // Check default value
    const skipInput = page.locator('input[type="number"]');
    await expect(skipInput).toHaveValue('6');
  });

  test('should allow changing skip lines value', async ({ page }) => {
    // Upload file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(vehiclesCsvFile());
    
    // Go to step 2
    await nextButton(page).click();
    
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
    await fileInput.setInputFiles(vehiclesCsvFile());
    
    // Go to step 2
    await nextButton(page).click();
    await expect(page.locator('h3:has-text("Configuration de l\'import")')).toBeVisible();
    
    // Go to step 3
    await nextButton(page).click();
    await expect(page.locator('text=Colonne CSV')).toBeVisible();
    
    // Go back to step 2
    await previousButton(page).click();
    await expect(page.locator('h3:has-text("Configuration de l\'import")')).toBeVisible();
    
    // Go back to step 1
    await previousButton(page).click();
    // L'`input[type="file"]` porte `style="display: none"` : il n'est jamais
    // visible. On atteste le retour à l'étape 1 sur la zone de dépôt.
    await expect(page.locator('.upload-area')).toBeVisible();
  });

  test('should complete full import flow', async ({ page }) => {
    // Mock the import API endpoint — route réelle : `/api/{dt}/import/vehicles`.
    await page.route('**/api/*/import/vehicles', async (route) => {
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
    await fileInput.setInputFiles(vehiclesCsvFile());
    await nextButton(page).click();

    // Step 2: Configuration (on conserve la valeur par défaut de skip lines).
    // L'attente est nécessaire : sans elle, le second « Suivant » cible un bouton
    // détaché pendant la transition du stepper.
    await expect(page.locator('h3:has-text("Configuration de l\'import")')).toBeVisible();
    await nextButton(page).click();
    
    // Step 3: Mapping (click import button)
    await page.locator('button:has-text("Importer"):visible').first().click();
    
    // Should show success message
    await expect(page.locator('.mat-mdc-snack-bar-container')).toContainText('Import terminé');
    
    // Should be on Step 4 (Result). On cible les libellés du panneau de résultat
    // et non un texte libre : « créés » et « mis à jour » apparaissent aussi dans
    // le snackbar, ce qui viole le mode strict.
    const statLabels = page.locator('.stat-label');
    await expect(statLabels.filter({ hasText: 'Véhicules créés' })).toBeVisible();
    await expect(statLabels.filter({ hasText: 'mis à jour' })).toBeVisible();
  });

  test('should cancel import and return to vehicles list', async ({ page }) => {
    // Upload file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(vehiclesCsvFile());
    
    // Click cancel button
    await page.locator('button:has-text("Annuler"):visible').first().click();
    
    // Should navigate back to vehicles list
    await expect(page).toHaveURL(/.*vehicles$/);
  });
});

