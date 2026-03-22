import { test, expect } from '@playwright/test';
import { setupApiMocks, mockAuthentication } from './helpers/mock-api';

/**
 * E2E Test: Admin - Dossiers Réparation
 * Tests: Vehicle → Dossiers tab → List / Create / Detail / Historique / Dépenses
 */
test.describe('Admin - Dossiers Réparation', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
    await mockAuthentication(page);
  });

  /**
   * Helper: Navigate to the vehicle edit page and click the "Dossiers Réparation" tab.
   */
  async function goToDossierTab(page: import('@playwright/test').Page) {
    await page.goto('http://localhost:4200/vehicles');
    await page.waitForSelector('table');
    // Click first vehicle row to open edit page
    await page.click('table tbody tr:first-child');
    await expect(page).toHaveURL(/.*vehicles\/.*\/edit/);
    // Click "Dossiers Réparation" tab
    await page.click('text=Dossiers Réparation');
  }

  test('should navigate to vehicle and see Dossiers Réparation tab', async ({ page }) => {
    await goToDossierTab(page);

    // Verify dossier list header is visible
    await expect(page.locator('text=Dossiers de réparation')).toBeVisible();

    // Check both dossiers are shown
    await expect(page.locator('text=REP-2026-001')).toBeVisible();
    await expect(page.locator('text=REP-2026-002')).toBeVisible();

    // Check status badges
    await expect(page.locator('.statut-ouvert:has-text("Ouvert")')).toBeVisible();
    await expect(page.locator('.statut-cloture:has-text("Clôturé")')).toBeVisible();

    // Check "Nouveau Dossier" button exists
    await expect(page.locator('button:has-text("Nouveau Dossier Réparation")')).toBeVisible();
  });

  test('should create a new dossier', async ({ page }) => {
    await goToDossierTab(page);

    // Click "Nouveau Dossier Réparation" button
    await page.getByRole('button', { name: 'Nouveau Dossier Réparation' }).click();

    // Wait for create form to appear
    await expect(page.locator('mat-card-title:has-text("Nouveau dossier de réparation")')).toBeVisible({ timeout: 5000 });

    // Fill first description item input
    await page.getByLabel('Élément 1').fill('Remplacement du pare-brise fissuré');

    // Submit create form
    await page.click('button:has-text("Créer le dossier")');

    // Verify success snackbar appears
    await expect(page.locator('.mat-mdc-snack-bar-container')).toContainText('Dossier créé avec succès');
  });

  test('should open dossier detail', async ({ page }) => {
    await goToDossierTab(page);

    // Click on dossier card REP-2026-001
    await page.click('mat-card:has-text("REP-2026-001")');

    // Verify detail view shows dossier info
    await expect(page.locator('mat-card-title:has-text("REP-2026-001")')).toBeVisible();
    await expect(page.locator('.statut-ouvert:has-text("Ouvert")')).toBeVisible();

    // Verify description items are shown as list
    await expect(page.locator('text=Réparation freins avant')).toBeVisible();
    await expect(page.locator('text=Plaquettes et disques usés')).toBeVisible();

    // Verify devis section with Garage Martin and 850€
    await expect(page.locator('.devis-table:has-text("Garage Martin")')).toBeVisible();
    await expect(page.locator('.devis-table:has-text("850")')).toBeVisible();

    // Verify facture section with 920€
    await expect(page.locator('.factures-table:has-text("920")')).toBeVisible();

    // Verify action buttons
    await expect(page.locator('button:has-text("Enregistrer un devis")')).toBeVisible();
    await expect(page.locator('button:has-text("Enregistrer une facture")')).toBeVisible();
    await expect(page.locator('button:has-text("Clôturer le dossier")')).toBeVisible();
  });

  test('should close dossier', async ({ page }) => {
    await goToDossierTab(page);

    // Click on dossier card
    await page.click('mat-card:has-text("REP-2026-001")');

    // Wait for detail to load
    await expect(page.locator('mat-card-title:has-text("REP-2026-001")')).toBeVisible();

    // Click "Clôturer le dossier"
    await page.click('button:has-text("Clôturer le dossier")');

    // Verify snackbar
    await expect(page.locator('.mat-mdc-snack-bar-container')).toBeVisible();
  });

  test('should show historique timeline', async ({ page }) => {
    await goToDossierTab(page);

    // Click on dossier card
    await page.click('mat-card:has-text("REP-2026-001")');

    // Wait for detail to load
    await expect(page.locator('text=Historique')).toBeVisible();

    // Verify timeline entries
    await expect(page.locator('text=Dossier créé')).toBeVisible();
    await expect(page.locator('text=Devis #1 - Garage Martin')).toBeVisible();
    await expect(page.locator('text=Approuvé par chef@croix-rouge.fr')).toBeVisible();
    await expect(page.locator('text=Facture #1 - Garage Martin')).toBeVisible();
  });

  test('should navigate back to list from detail', async ({ page }) => {
    await goToDossierTab(page);

    // Click on dossier card
    await page.click('mat-card:has-text("REP-2026-001")');
    await expect(page.locator('mat-card-title:has-text("REP-2026-001")')).toBeVisible();

    // Click back button
    await page.getByRole('button', { name: /Retour/ }).click();

    // Verify list is shown again
    await expect(page.locator('h3:has-text("Dossiers de réparation")')).toBeVisible({ timeout: 5000 });
  });

  test('should show Dépenses tab', async ({ page }) => {
    await page.goto('http://localhost:4200/vehicles');
    await page.waitForSelector('table');
    await page.click('table tbody tr:first-child');
    await expect(page).toHaveURL(/.*vehicles\/.*\/edit/);

    // Click "Dépenses" tab
    await page.getByRole('tab', { name: 'Dépenses' }).click();

    // Verify summary shows total amounts (use specific locator to avoid strict mode)
    await expect(page.locator('.summary-value').first()).toBeVisible();
    await expect(page.locator('.summary-value:has-text("920")').first()).toBeVisible();

    // Verify year 2026 is shown in a card title
    await expect(page.locator('mat-card-title:has-text("2026")')).toBeVisible();
  });
});

