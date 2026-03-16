import { Page } from '@playwright/test';
import { mockVehicles, mockUser, mockReservations } from '../fixtures/mock-data';

/**
 * Setup API mocks for E2E tests
 * Intercepts backend API calls and returns mock data
 */
export async function setupApiMocks(page: Page) {
  // Mock auth endpoints
  await page.route('**/api/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockUser),
    });
  });

  await page.route('**/api/auth/login', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: 'mock-token',
        token_type: 'bearer',
        user: mockUser,
      }),
    });
  });

  // Mock vehicles endpoints
  await page.route('**/api/vehicles', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ vehicles: mockVehicles }),
    });
  });

  await page.route('**/api/vehicles/*', async (route) => {
    const url = route.request().url();
    const nomSynthetique = url.split('/').pop()?.split('?')[0];
    const vehicle = mockVehicles.find((v) => v.nom_synthetique === nomSynthetique);

    if (vehicle) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(vehicle),
      });
    } else {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Vehicle not found' }),
      });
    }
  });

  // Mock calendar endpoints
  await page.route('**/api/calendar/events**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ events: mockReservations }),
    });
  });

  await page.route('**/api/calendar/reservations', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'new-res-' + Date.now(),
          message: 'Reservation created successfully',
        }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ reservations: mockReservations }),
      });
    }
  });

  // Mock carnet de bord endpoints
  await page.route('**/api/carnet-bord/prise', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        message: 'Prise enregistrée avec succès',
        sheet_url: 'https://docs.google.com/spreadsheets/d/mock-sheet',
      }),
    });
  });

  await page.route('**/api/carnet-bord/retour', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        message: 'Retour enregistré avec succès',
        sheet_url: 'https://docs.google.com/spreadsheets/d/mock-sheet',
      }),
    });
  });

  // Mock config endpoints
  await page.route('**/api/config', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        template_document_vehicule_url: 'https://docs.google.com/document/d/test',
        sheets_url_vehicules: 'https://docs.google.com/spreadsheets/d/test-vehicules',
        sheets_url_benevoles: 'https://docs.google.com/spreadsheets/d/test-benevoles',
        sheets_url_responsables: 'https://docs.google.com/spreadsheets/d/test-responsables',
        email_destinataire_alertes: 'alerts@croix-rouge.fr',
      }),
    });
  });

  // Mock vehicle import endpoint
  await page.route('**/api/vehicles/import', async (route) => {
    if (route.request().method() === 'POST') {
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
    } else {
      await route.continue();
    }
  });
}

/**
 * Mock successful authentication
 */
export async function mockAuthentication(page: Page) {
  // Set auth token in localStorage
  await page.addInitScript(() => {
    localStorage.setItem('auth_token', 'mock-token');
    localStorage.setItem('user', JSON.stringify({
      email: 'test@croix-rouge.fr',
      nom: 'Test',
      prenom: 'User',
      ul: 'UL Paris 15',
      role: 'Responsable UL',
    }));
  });
}

