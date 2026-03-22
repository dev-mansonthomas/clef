import { test, expect } from '@playwright/test';
import { setupApiMocks } from './helpers/mock-api';

/**
 * E2E Test: Approbation Page — Multi-devis with grouped decision
 * Tests: Display multiple devis, approve all, reject all
 */
test.describe('Approbation Page', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
    // Auth is mocked via setupApiMocks (/auth/me returns mockUser)
    // mockUser.email matches mockApprobationData.valideur_email
  });

  test('should display devis details and decision radio buttons', async ({ page }) => {
    await page.goto('http://localhost:4200/approbation/test-token-123');

    // Wait for data to load
    await expect(page.getByText('Garage Martin').first()).toBeVisible({ timeout: 10000 });

    // Verify both devis are shown
    await expect(page.getByText('Auto Service Plus').first()).toBeVisible();

    // Verify devis amounts
    await expect(page.locator('text=850')).toBeVisible();
    await expect(page.locator('text=620')).toBeVisible();

    // Verify dossier info
    await expect(page.locator('text=REP-2026-001')).toBeVisible();
    await expect(page.locator('text=Réparation freins avant')).toBeVisible();

    // Verify Drive link is visible for the first devis
    await expect(page.locator('text=Voir le devis')).toBeVisible();

    // Verify decision radio buttons
    await expect(page.locator('text=Approuver tout')).toBeVisible();
    await expect(page.locator('text=Refuser tout')).toBeVisible();
    await expect(page.locator('text=Approbation partielle')).toBeVisible();

    // Verify confirm button
    await expect(page.locator('button:has-text("Confirmer ma décision")')).toBeVisible();
  });

  test('should approve all devis', async ({ page }) => {
    await page.goto('http://localhost:4200/approbation/test-token-123');

    // Wait for data to load — "Approuver tout" is selected by default
    await expect(page.locator('text=Approuver tout')).toBeVisible({ timeout: 10000 });

    // Click confirm
    await page.click('button:has-text("Confirmer ma décision")');

    // Verify confirmation message
    await expect(page.locator('text=devis traité')).toBeVisible();
    await expect(page.locator('text=Vous pouvez fermer cette page')).toBeVisible();
  });

  test('should reject all devis', async ({ page }) => {
    await page.goto('http://localhost:4200/approbation/test-token-123');

    // Wait for data to load
    await expect(page.locator('text=Refuser tout')).toBeVisible({ timeout: 10000 });

    // Select "Refuser tout"
    await page.locator('mat-radio-button:has-text("Refuser tout")').click();

    // Commentaire is required for refus — fill it in
    await page.locator('textarea').fill('Trop cher');

    // Click confirm
    await page.click('button:has-text("Confirmer ma décision")');

    // Verify confirmation message
    await expect(page.locator('text=devis traité')).toBeVisible();
    await expect(page.locator('text=Vous pouvez fermer cette page')).toBeVisible();
  });
});

