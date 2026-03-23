import { Page } from '@playwright/test';
import { mockVehicles, mockUser, mockReservations, mockDossiers, mockFournisseurs, mockValideurs, mockContactsCC, mockHistorique, mockDepenses, mockApprobationData } from '../fixtures/mock-data';

/**
 * Setup API mocks for E2E tests
 * Intercepts backend API calls and returns mock data
 */
export async function setupApiMocks(page: Page) {
  // Mock auth endpoints (auth routes have no /api prefix)
  await page.route('**/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockUser),
    });
  });

  await page.route('**/auth/login', async (route) => {
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
    const identifier = url.split('/').pop()?.split('?')[0];
    const vehicle = mockVehicles.find((v) => v.nom_synthetique === identifier || v.immat === identifier);

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

  // Mock drive-documents endpoint
  await page.route('**/api/vehicles/*/drive-documents', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ documents: [] }),
    });
  });

  // Mock UL config endpoint
  await page.route('**/api/*/ul-config/**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) });
  });

  // Mock dossiers-reparation list/create
  await page.route('**/api/*/vehicles/*/dossiers-reparation', async (route) => {
    if (route.request().method() === 'POST') {
      const postBody = JSON.parse(route.request().postData() || '{}');
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          numero: 'REP-2026-003',
          immat: 'AB-123-CD',
          dt: 'DT75',
          titre: postBody.titre || null,
          description: postBody.description || 'Nouveau dossier',
          statut: 'ouvert',
          cree_par: 'test@croix-rouge.fr',
          cree_le: new Date().toISOString(),
          devis: [],
          factures: []
        }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ dossiers: mockDossiers, total: mockDossiers.length }),
      });
    }
  });

  // Bulk approval endpoint
  await page.route('**/api/*/vehicles/*/dossiers-reparation/*/send-bulk-approval', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          count: 1,
          token: 'mock-dossier-token-1',
          valideur_email: 'chef@croix-rouge.fr',
          message: '1 devis envoyés pour approbation',
        }),
      });
    }
  });

  // Single dossier
  await page.route('**/api/*/vehicles/*/dossiers-reparation/REP-*', async (route) => {
    const method = route.request().method();
    const url = route.request().url();

    // Skip if it's a sub-resource (devis, factures, historique, send-bulk-approval)
    if (url.includes('/devis') || url.includes('/factures') || url.includes('/historique') || url.includes('/send-bulk-approval')) {
      return route.fallback();
    }

    if (method === 'PATCH') {
      const body = JSON.parse(route.request().postData() || '{}');
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...mockDossiers[0], ...body }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockDossiers[0]),
      });
    }
  });

  // Devis endpoints
  await page.route('**/api/*/vehicles/*/dossiers-reparation/*/devis', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'd-002',
          date_devis: '2026-03-21',
          fournisseur: { id: 'f-001', nom: 'Garage Martin' },
          description: 'Test devis',
          montant: 500.00,
          statut: 'en_attente',
          cree_par: 'test@croix-rouge.fr',
          cree_le: new Date().toISOString()
        }),
      });
    }
  });

  // Devis annuler endpoint
  await page.route('**/api/*/vehicles/*/dossiers-reparation/*/devis/*/annuler', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'd-001',
          date_devis: '2026-03-16',
          fournisseur: { id: 'f-001', nom: 'Garage Martin' },
          description: 'Remplacement plaquettes et disques avant',
          montant: 850.00,
          statut: 'annule',
          cree_par: 'test@croix-rouge.fr',
          cree_le: '2026-03-16T11:00:00Z'
        }),
      });
    } else {
      await route.fallback();
    }
  });

  // Devis file upload endpoint
  await page.route('**/api/*/vehicles/*/dossiers-reparation/*/devis/*/upload', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'd-001',
          date_devis: '2026-03-16',
          fournisseur: { id: 'f-001', nom: 'Garage Martin' },
          description: 'Remplacement plaquettes et disques avant',
          montant: 850.00,
          statut: 'approuve',
          fichier: { file_id: 'mock-file-devis-1', name: 'Devis-d-001-Garage Martin.pdf', web_view_link: 'https://drive.google.com/file/d/mock-file-devis-1/view' },
          cree_par: 'test@croix-rouge.fr',
          cree_le: '2026-03-16T11:00:00Z'
        }),
      });
    } else {
      await route.fallback();
    }
  });

  // Single devis endpoint (PATCH for edit)
  await page.route('**/api/*/vehicles/*/dossiers-reparation/*/devis/*', async (route) => {
    const url = route.request().url();
    // Skip sub-resources like send-approval, upload, annuler
    if (url.includes('/send-approval') || url.includes('/upload') || url.includes('/annuler')) {
      return route.fallback();
    }
    if (route.request().method() === 'PATCH') {
      const body = JSON.parse(route.request().postData() || '{}');
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'd-001',
          date_devis: body.date_devis || '2026-03-16',
          fournisseur: { id: body.fournisseur_id || 'f-001', nom: body.fournisseur_nom || 'Garage Martin' },
          description: body.description_travaux || 'Remplacement plaquettes et disques avant',
          montant: body.montant || 850.00,
          statut: body.statut || 'en_attente',
          cree_par: 'test@croix-rouge.fr',
          cree_le: '2026-03-16T11:00:00Z'
        }),
      });
    } else {
      await route.fallback();
    }
  });

  // Facture file upload endpoint
  await page.route('**/api/*/vehicles/*/dossiers-reparation/*/factures/*/upload', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'fac-001',
          date_facture: '2026-03-20',
          fournisseur: { id: 'f-001', nom: 'Garage Martin' },
          classification: 'entretien_courant',
          description: 'Remplacement plaquettes et disques avant',
          montant_total: 920.00,
          montant_crf: 920.00,
          devis_id: 'd-001',
          fichier: { file_id: 'mock-file-facture-1', name: 'Facture 01 - Garage Martin.pdf', web_view_link: 'https://drive.google.com/file/d/mock-file-facture-1/view' },
          cree_par: 'test@croix-rouge.fr',
          cree_le: '2026-03-20T15:00:00Z'
        }),
      });
    } else {
      await route.fallback();
    }
  });

  // Single facture endpoint (PATCH for edit)
  await page.route('**/api/*/vehicles/*/dossiers-reparation/*/factures/*', async (route) => {
    const url = route.request().url();
    // Skip sub-resources like upload
    if (url.includes('/upload')) {
      return route.fallback();
    }
    if (route.request().method() === 'PATCH') {
      const body = JSON.parse(route.request().postData() || '{}');
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'fac-001',
          date_facture: body.date_facture || '2026-03-20',
          fournisseur: { id: body.fournisseur_id || 'f-001', nom: body.fournisseur_nom || 'Garage Martin' },
          classification: body.classification || 'entretien_courant',
          description: body.description_travaux || 'Remplacement plaquettes et disques avant',
          montant_total: body.montant_total || 920.00,
          montant_crf: body.montant_crf || 920.00,
          devis_id: body.devis_id || 'd-001',
          cree_par: 'test@croix-rouge.fr',
          cree_le: '2026-03-20T15:00:00Z'
        }),
      });
    } else {
      await route.fallback();
    }
  });

  // Factures endpoints
  await page.route('**/api/*/vehicles/*/dossiers-reparation/*/factures', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'fac-002',
          date_facture: '2026-03-21',
          fournisseur: { id: 'f-001', nom: 'Garage Martin' },
          classification: 'entretien_courant',
          description: 'Test facture',
          montant_total: 600.00,
          montant_crf: 600.00,
          warning_no_devis: false,
          cree_par: 'test@croix-rouge.fr',
          cree_le: new Date().toISOString()
        }),
      });
    }
  });

  // Historique endpoint
  await page.route('**/api/*/vehicles/*/dossiers-reparation/*/historique', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockHistorique),
    });
  });

  // Fournisseurs endpoints
  await page.route('**/api/*/fournisseurs', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'f-new', nom: 'Nouveau Garage', scope: 'dt' }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ fournisseurs: mockFournisseurs, total: mockFournisseurs.length }),
      });
    }
  });

  // Valideurs endpoints
  await page.route('**/api/*/valideurs', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'v-new', prenom: 'Nouveau', nom: 'Valideur', email: 'new@croix-rouge.fr', actif: true, cree_par: 'test@croix-rouge.fr', cree_le: new Date().toISOString() }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ valideurs: mockValideurs, count: mockValideurs.length }),
      });
    }
  });

  await page.route('**/api/*/valideurs/*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockValideurs[0]),
    });
  });

  // Contacts CC endpoints
  await page.route('**/api/*/contacts-cc', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'cc-new', prenom: 'Nouveau', nom: 'Contact', email: 'new-cc@croix-rouge.fr', actif: true, cc_par_defaut: false, cree_par: 'test@croix-rouge.fr', cree_le: new Date().toISOString() }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ contacts_cc: mockContactsCC, count: mockContactsCC.length }),
      });
    }
  });

  await page.route('**/api/*/contacts-cc/*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockContactsCC[0]),
    });
  });

  // Depenses endpoint
  await page.route('**/api/*/vehicles/*/depenses', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockDepenses),
    });
  });

  // Approbation endpoints (public) — dossier-level tokens
  await page.route('**/api/approbation/*', async (route) => {
    if (route.request().method() === 'POST') {
      const postBody = JSON.parse(route.request().postData() || '{}');
      // Detect old vs new format
      if ('decision' in postBody && !('mode' in postBody)) {
        // Old format (single devis)
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ decision: postBody.decision, message: `Devis ${postBody.decision === 'approuve' ? 'approuvé' : 'refusé'} avec succès` }),
        });
      } else {
        // New format (dossier-level)
        const results = mockApprobationData.devis_ids.map((id: string) => ({
          devis_id: id,
          decision: postBody.mode === 'refuse_tout' ? 'refuse' : 'approuve',
          status: postBody.mode === 'refuse_tout' ? 'refusé' : 'approuvé',
        }));
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ results, message: `${results.length} devis traité(s)` }),
        });
      }
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockApprobationData),
      });
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

