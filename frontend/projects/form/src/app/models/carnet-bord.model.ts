/**
 * Models for vehicle pickup and return forms (carnet de bord)
 */

export interface RetourVehiculeForm {
  // Vehicle identification
  nomSynthetique: string;
  indicatif: string;
  
  // Return data
  kmArrivee: number;
  niveauCarburant: string; // '1/4', '1/2', '3/4', 'Plein'
  etatGeneral: string; // 'Bon', 'Moyen', 'Mauvais'
  
  // Problem reporting
  problemeASignaler: boolean;
  descriptionProbleme?: string;
  
  // Photos
  photosProblemes?: File[];
  
  // Metadata
  dateRetour: Date;
  emailBenevole: string;
  nomBenevole: string;
}

export interface RetourVehiculeRequest {
  vehicule_id: string;
  benevole_email: string;
  benevole_nom: string;
  benevole_prenom: string;
  kilometrage: number;
  niveau_carburant: string;
  etat_general: string;
  problemes_signales?: string;
  observations?: string;
  timestamp?: string; // ISO 8601
}

export interface RetourVehiculeResponse {
  success: boolean;
  message: string;
  spreadsheet_id?: string;
  perimetre?: string;
}

export interface PriseVehiculeData {
  vehicule_id: string;
  nomSynthetique: string;
  benevole_nom: string;
  benevole_prenom: string;
  kilometrage: number;
  niveau_carburant: string;
  etat_general: string;
  observations: string;
  timestamp: string;
  datePrise?: string;
}

export const NIVEAUX_CARBURANT = [
  { value: '1/4', label: '1/4' },
  { value: '1/2', label: '1/2' },
  { value: '3/4', label: '3/4' },
  { value: 'Plein', label: 'Plein' }
];

export const ETATS_GENERAL = [
  { value: 'Bon', label: 'Bon' },
  { value: 'Moyen', label: 'Moyen' },
  { value: 'Mauvais', label: 'Mauvais' }
];

/**
 * Prise (Pickup) form models
 */
export interface PriseVehiculeForm {
  // Vehicle identification
  nomSynthetique: string;
  indicatif: string;

  // Pickup data
  kmDepart: number;
  niveauCarburant: string; // '0', '1/8', '1/4', '3/8', '1/2', '5/8', '3/4', '7/8', 'Plein'
  etatGeneral: number; // 1-5 rating
  commentaires: string;

  // Photos (up to 5)
  photos: File[];

  // Signature
  signatureDataUrl: string;

  // Metadata
  datePrise: Date;
  emailBenevole: string;
  nomBenevole: string;
}

export interface PriseVehiculeRequest {
  nomSynthetique: string;
  kmDepart: number;
  niveauCarburant: string;
  etatGeneral: number;
  commentaires: string;
  signature: string; // Base64 data URL
  datePrise: string; // ISO 8601
  emailBenevole: string;
  nomBenevole: string;
}

export interface PriseVehiculeResponse {
  success: boolean;
  message: string;
  spreadsheetId?: string;
  rowNumber?: number;
  photoUrls?: string[];
}

// Fuel gauge levels for prise form (more granular)
export const NIVEAUX_CARBURANT_PRISE = [
  { value: '0', label: 'Vide' },
  { value: '1/8', label: '1/8' },
  { value: '1/4', label: '1/4' },
  { value: '3/8', label: '3/8' },
  { value: '1/2', label: '1/2' },
  { value: '5/8', label: '5/8' },
  { value: '3/4', label: '3/4' },
  { value: '7/8', label: '7/8' },
  { value: 'Plein', label: 'Plein' }
];

