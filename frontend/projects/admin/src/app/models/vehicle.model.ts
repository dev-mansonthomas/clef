/**
 * Vehicle models matching backend API structure
 */

export type StatusColor = 'red' | 'orange' | 'green';

export type DisponibiliteStatus = 'Dispo' | 'Indispo';

export type SuiviMode = 'prise' | 'retour' | 'prise_et_retour';

export type VehicleDocumentType =
  | 'carte_grise'
  | 'carte_total'
  | 'plan_entretien'
  | 'factures'
  | 'assurance'
  | 'controle_technique'
  | 'carnet_suivi';

export type ManagedVehicleDocumentType = 'carte_grise' | 'carte_total' | 'plan_entretien' | 'assurance';

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

export interface VehicleDriveFile {
  file_id: string;
  name: string;
  web_view_link?: string | null;
  mime_type?: string | null;
  created_time?: string | null;
  selected_at?: string | null;
  folder_id?: string | null;
  folder_name?: string | null;
}

export interface VehicleDriveDocument {
  key: VehicleDocumentType;
  label: string;
  folder_name: string;
  managed: boolean;
  folder_id?: string | null;
  folder_url?: string | null;
  file_count: number;
  current_file?: VehicleDriveFile | null;
}

export interface VehicleDriveDocumentsResponse {
  configured: boolean;
  root_folder_id?: string | null;
  root_folder_url?: string | null;
  vehicle_folder_name: string;
  vehicle_folder_id?: string | null;
  vehicle_folder_url?: string | null;
  documents: Record<VehicleDocumentType, VehicleDriveDocument>;
}

export interface VehicleDriveFileListResponse {
  files: VehicleDriveFile[];
}

export interface VehicleListResponse {
  count: number;
  vehicles: Vehicle[];
}

