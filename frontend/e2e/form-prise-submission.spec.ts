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

    // Should show vehicle selector.
    // L'écran rend `<mat-card-title>Sélection du Véhicule</mat-card-title>` — avec
    // un V majuscule — et non un `<h2>` : l'ancienne assertion ne pouvait pas
    // passer (vehicle-selector.component.html:4).
    await expect(page.getByText('Sélection du Véhicule')).toBeVisible();

    // Wait for vehicles to load
    await page.waitForSelector('mat-select');

    // Select a vehicle. La sélection passe par le `mat-select` de la section
    // « Sélection Manuelle » : le gabarit n'a jamais proposé de cartes véhicule
    // cliquables, ce que l'ancienne version du test supposait.
    await page.locator('mat-select').click();
    await page.locator('mat-option', { hasText: 'VL75-01' }).click();

    // Should navigate to prise form. `navigateToForm` utilise
    // l'**immatriculation** (vehicle-selector.component.ts:213), pas le nom
    // synthétique : la route est `/prise/AB-123-CD`.
    await expect(page).toHaveURL(/.*prise\/AB-123-CD/);
    await expect(page.getByText('Prise de Véhicule')).toBeVisible();

    // Verify vehicle info is displayed. Le sous-titre affiche l'immatriculation
    // issue de la route ; la marque et le modèle ne sont pas rendus sur cet écran.
    await expect(page.getByText('AB-123-CD').first()).toBeVisible();

    // Fill in the prise form
    await page.fill('input[formcontrolname="kmDepart"]', '12500');

    // Select fuel level
    await page.click('mat-select[formcontrolname="niveauCarburant"]');
    await page.click('mat-option:has-text("3/4")');

    // ⚠️ Attendre la disparition du backdrop de l'overlay Material avant de
    // dessiner : tant qu'il est présent, il intercepte le `pointerdown` et le pad
    // de signature reste vide. Le formulaire est alors rejeté par
    // « Veuillez signer le formulaire », sans que la cause soit visible.
    await expect(page.locator('.cdk-overlay-backdrop')).toHaveCount(0);

    // `etatGeneral` est un `mat-slider` déjà initialisé à 5 par le formulaire
    // (prise-form.component.ts:82) : rien à saisir, et `fill()` échouerait sur un
    // `input[type=range]`.

    // Add comments
    await page.fill('textarea[formcontrolname="commentaires"]', 'Véhicule en bon état');

    // Signature : obligatoire (`signaturePad.isEmpty()` bloque la soumission).
    // Un `mouse.move` interpolé émet assez de `pointermove` pour que SignaturePad
    // enregistre un tracé.
    const signatureCanvas = page.locator('canvas').first();
    await signatureCanvas.scrollIntoViewIfNeeded();
    const box = (await signatureCanvas.boundingBox())!;
    await page.mouse.move(box.x + box.width * 0.2, box.y + box.height * 0.5);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.3, { steps: 10 });
    await page.mouse.move(box.x + box.width * 0.8, box.y + box.height * 0.7, { steps: 10 });
    await page.mouse.up();

    // Submit the form
    await page.click('button[type="submit"]:has-text("Valider")');

    // Should show success message. Le libellé exact est « Prise de véhicule
    // enregistrée avec succès » (prise-form.component.ts:220) — au féminin.
    await expect(page.locator('.mat-mdc-snack-bar-container')).toContainText('enregistrée avec succès', {
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
      // `.mat-error` est l'ancien nom de classe : Angular Material MDC rend
      // `<mat-error class="mat-mdc-form-field-error">`. On cible l'élément, dont
      // l'apparition est garantie par `markAllAsTouched()` dans `onSubmit()`.
      await expect(page.locator('mat-error, .error-message').first()).toBeVisible();
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

    // L'ancien sélecteur combiné `button, input[type=file]` correspondait à deux
    // éléments et violait le mode strict. L'input est le seul point d'entrée utile,
    // et `setInputFiles` fonctionne même sur un input masqué.
    const fileInput = page.locator('input[type="file"]');
    await expect(fileInput).toHaveCount(1);

    {
      {
        // Set files on the input
        await fileInput.setInputFiles({
          name: 'test-photo.jpg',
          mimeType: 'image/jpeg',
          buffer: Buffer.from('fake-image-data'),
        });

        // Verify photo was added
        await expect(page.locator('.photo-preview').first()).toBeVisible();
      }
    }
  });
});

