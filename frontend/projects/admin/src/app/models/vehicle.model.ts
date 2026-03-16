/**
 * Vehicle models matching backend API structure
 */

export type StatusColor = 'red' | 'orange' | 'green';

export type DisponibiliteStatus = 'Dispo' | 'Indispo';

export type SuiviMode = 'prise' | 'retour' | 'prise_et_retour';

export interface StatusInfo {
  value: string;
  color: StatusColor;
  days_until_expiry?: number | null;
}

export interface Vehicle {
  // Base fields (19 columns from referential)
  dt_ul: string;
  immat: string;
  indicatif: string;
  operationnel_mecanique: DisponibiliteStatus;
  raison_indispo: string;
  prochain_controle_technique: string | null;
  prochain_controle_pollution: string | null;
  marque: string;
  modele: string;
  type: string;
  date_mec: string | null;
  nom_synthetique: string;
  carte_grise: string;
  nb_places: string;
  commentaires: string;
  lieu_stationnement: string;
  instructions_recuperation: string;
  assurance_2026: string;
  numero_serie_baus: string;
  suivi_mode: SuiviMode;  // Backend now provides type-based default

  // Computed status fields
  status_ct: StatusInfo;
  status_pollution: StatusInfo;
  status_disponibilite: StatusInfo;
}

export interface VehicleUpdate {
  couleur_calendrier?: string | null;
  commentaires?: string | null;
  suivi_mode?: SuiviMode | null;
}

export interface VehicleListResponse {
  count: number;
  vehicles: Vehicle[];
}

