/**
 * Mock data for E2E tests
 * Matches the backend mock data structure
 */

export const mockVehicles = [
  {
    dt_ul: 'UL Paris 15',
    immat: 'AB-123-CD',
    indicatif: 'VL75-01',
    operationnel_mecanique: 'Dispo',
    raison_indispo: '',
    prochain_controle_technique: '2026-06-15',
    prochain_controle_pollution: '2026-06-15',
    marque: 'Renault',
    modele: 'Kangoo',
    type: 'VL',
    date_mec: '2020-01-15',
    nom_synthetique: 'VL75-01-KANGOO',
    carte_grise: 'CG123456',
    nb_places: '5',
    commentaires: 'Véhicule de liaison',
    lieu_stationnement: 'Garage UL Paris 15',
    instructions_recuperation: 'https://docs.google.com/document/d/test1',
    assurance_2026: 'OK',
    numero_serie_baus: 'BAUS001',
    couleur_calendrier: '#FF5733',
    status_ct: 'green',
    status_pollution: 'green',
    status_disponibilite: 'green'
  },
  {
    dt_ul: 'UL Paris 15',
    immat: 'EF-456-GH',
    indicatif: 'VL75-02',
    operationnel_mecanique: 'Dispo',
    raison_indispo: '',
    prochain_controle_technique: '2026-03-20',
    prochain_controle_pollution: '2026-03-20',
    marque: 'Peugeot',
    modele: 'Partner',
    type: 'VL',
    date_mec: '2019-05-10',
    nom_synthetique: 'VL75-02-PARTNER',
    carte_grise: 'CG789012',
    nb_places: '5',
    commentaires: 'Véhicule de transport',
    lieu_stationnement: 'Garage UL Paris 15',
    instructions_recuperation: 'https://docs.google.com/document/d/test2',
    assurance_2026: 'OK',
    numero_serie_baus: 'BAUS002',
    couleur_calendrier: '#33C3FF',
    status_ct: 'orange',
    status_pollution: 'orange',
    status_disponibilite: 'green'
  }
];

export const mockUser = {
  email: 'test@croix-rouge.fr',
  nom: 'Test',
  prenom: 'User',
  ul: 'UL Paris 15',
  role: 'Responsable UL',
  perimetre: 'UL Paris 15',
  type_perimetre: 'UL'
};

export const mockReservations = [
  {
    id: 'res-1',
    vehicule_id: 'VL75-01-KANGOO',
    indicatif: 'VL75-01',
    chauffeur_nom: 'Dupont',
    chauffeur_prenom: 'Jean',
    mission: 'Mission Secours',
    date_debut: new Date(Date.now() + 86400000).toISOString(), // Tomorrow
    date_fin: new Date(Date.now() + 90000000).toISOString(),
    commentaire: 'Transport matériel',
    couleur: '#FF5733'
  }
];

export const mockDossiers = [
  {
    numero: 'REP-2026-001',
    immat: 'AB-123-CD',
    dt: 'DT75',
    titre: 'Freins avant usés',
    description: ['Réparation freins avant', 'Plaquettes et disques usés'],
    statut: 'ouvert',
    cree_par: 'test@croix-rouge.fr',
    cree_le: '2026-03-15T10:30:00Z',
    devis: [
      {
        id: 'd-001',
        date_devis: '2026-03-16',
        fournisseur: { id: 'f-001', nom: 'Garage Martin' },
        description: 'Remplacement plaquettes et disques avant',
        montant: 850.00,
        statut: 'approuve',
        valideur_email: 'chef@croix-rouge.fr',
        date_decision: '2026-03-17T14:00:00Z',
        cree_par: 'test@croix-rouge.fr',
        cree_le: '2026-03-16T11:00:00Z'
      }
    ],
    factures: [
      {
        id: 'fac-001',
        date_facture: '2026-03-20',
        fournisseur: { id: 'f-001', nom: 'Garage Martin' },
        classification: 'entretien_courant',
        description: 'Remplacement plaquettes et disques avant',
        montant_total: 920.00,
        montant_crf: 920.00,
        devis_id: 'd-001',
        cree_par: 'test@croix-rouge.fr',
        cree_le: '2026-03-20T15:00:00Z'
      }
    ]
  },
  {
    numero: 'REP-2026-002',
    immat: 'EF-456-GH',
    dt: 'DT75',
    titre: 'Carrosserie passager',
    description: ['Carrosserie abîmée côté passager'],
    statut: 'cloture',
    cree_par: 'test@croix-rouge.fr',
    cree_le: '2026-02-10T08:00:00Z',
    devis: [],
    factures: []
  }
];

export const mockFournisseurs = [
  { id: 'f-001', nom: 'Garage Martin', telephone: '01 23 45 67 89', email: 'contact@garage-martin.fr', scope: 'dt' },
  { id: 'f-002', nom: 'Auto Service Plus', telephone: '01 98 76 54 32', email: 'info@autoservice.fr', scope: 'ul', scope_id: 'UL Paris 15' }
];

export const mockValideurs = [
  { id: 'v-001', prenom: 'Chef', nom: 'Dupont', email: 'chef@croix-rouge.fr', role: 'Responsable logistique', actif: true, principal: true, cree_par: 'admin@croix-rouge.fr', cree_le: '2026-01-01T00:00:00Z' },
  { id: 'v-002', prenom: 'Marie', nom: 'Martin', email: 'marie.martin@croix-rouge.fr', role: 'Directrice DT', actif: true, principal: false, cree_par: 'admin@croix-rouge.fr', cree_le: '2026-01-01T00:00:00Z' }
];

export const mockContactsCC = [
  { id: 'cc-001', prenom: 'Jean', nom: 'Durand', email: 'jean.durand@croix-rouge.fr', role: 'Comptable', actif: true, cc_par_defaut: true, cree_par: 'admin@croix-rouge.fr', cree_le: '2026-01-01T00:00:00Z' },
  { id: 'cc-002', prenom: 'Sophie', nom: 'Leroy', email: 'sophie.leroy@croix-rouge.fr', role: 'Assistante', actif: true, cc_par_defaut: false, cree_par: 'admin@croix-rouge.fr', cree_le: '2026-01-01T00:00:00Z' }
];

export const mockHistorique = [
  { date: '2026-03-20T15:00:00Z', auteur: 'test@croix-rouge.fr', action: 'facture_ajoutee', details: 'Facture #1 - Garage Martin - 920.00€ TTC', ref: 'DT75:vehicules:AB-123-CD:travaux:REP-2026-001' },
  { date: '2026-03-17T14:00:00Z', auteur: 'chef@croix-rouge.fr', action: 'devis_approuve', details: 'Approuvé par chef@croix-rouge.fr', ref: 'DT75:vehicules:AB-123-CD:travaux:REP-2026-001' },
  { date: '2026-03-16T11:00:00Z', auteur: 'test@croix-rouge.fr', action: 'devis_ajoute', details: 'Devis #1 - Garage Martin - 850.00€', ref: 'DT75:vehicules:AB-123-CD:travaux:REP-2026-001' },
  { date: '2026-03-15T10:30:00Z', auteur: 'test@croix-rouge.fr', action: 'creation', details: 'Dossier créé', ref: 'DT75:vehicules:AB-123-CD:travaux:REP-2026-001' }
];

export const mockDepenses = {
  years: [
    {
      year: 2026,
      nb_dossiers: 1,
      total_cout: 920.00,
      total_crf: 920.00,
      factures: [
        { date: '2026-03-20', numero_dossier: 'REP-2026-001', description: 'Remplacement plaquettes et disques avant', fournisseur_nom: 'Garage Martin', classification: 'entretien_courant', montant_total: 920.00, montant_crf: 920.00 }
      ]
    }
  ],
  total_all_years_cout: 920.00,
  total_all_years_crf: 920.00
};

export const mockApprobationData = {
  devis: [
    {
      id: 'd-001',
      date_devis: '2026-03-16',
      fournisseur: { id: 'f-001', nom: 'Garage Martin' },
      description: 'Remplacement plaquettes et disques avant',
      description_items: ['Plaquettes avant', 'Disques avant'],
      montant: 850.00,
      statut: 'envoye',
      fichier: {
        file_id: 'mock-file-123',
        name: 'Devis 01 - Garage Martin.pdf',
        web_view_link: 'https://drive.google.com/file/d/mock-file-123/view',
      },
      cree_par: 'test@croix-rouge.fr',
      cree_le: '2026-03-16T11:00:00Z'
    },
    {
      id: 'd-002',
      date_devis: '2026-03-17',
      fournisseur: { id: 'f-002', nom: 'Auto Service Plus' },
      description: 'Remplacement disques avant uniquement',
      description_items: ['Disques avant'],
      montant: 620.00,
      statut: 'envoye',
      cree_par: 'test@croix-rouge.fr',
      cree_le: '2026-03-17T09:00:00Z'
    }
  ],
  devis_ids: ['d-001', 'd-002'],
  dossier_description: ['Réparation freins avant', 'Plaquettes et disques usés'],
  dossier_titre: 'Freins avant',
  numero_dossier: 'REP-2026-001',
  immat: 'AB-123-CD',
  dt: 'DT75',
  valideur_email: 'test@croix-rouge.fr',
  status: 'pending',
  created_at: '2026-03-16T12:00:00Z',
  expires_at: '2026-03-23T12:00:00Z'
};
