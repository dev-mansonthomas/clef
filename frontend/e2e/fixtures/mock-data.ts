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

