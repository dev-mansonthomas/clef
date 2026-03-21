/**
 * Repair dossier models matching backend API structure
 */

export interface DossierReparation {
  numero: string;  // REP-2026-001
  description: string;
  statut: 'ouvert' | 'cloture' | 'annule';
  date_creation: string;
  photos?: string[];
  sinistre_ref?: string;
  devis: Devis[];
  factures: Facture[];
}

export interface Devis {
  id: number;
  date_devis: string;
  fournisseur_id: string;
  fournisseur_nom?: string;
  description_travaux: string;
  montant: number;
  statut: 'en_attente' | 'envoye' | 'approuve' | 'refuse' | 'annule';
  valideur_email?: string;
  date_decision?: string;
  fichier_drive_id?: string;
  fichier_drive_url?: string;
}

export interface Facture {
  id: number;
  date_facture: string;
  fournisseur_id: string;
  fournisseur_nom?: string;
  classification: string;
  description_travaux: string;
  montant_total: number;
  montant_crf: number;
  devis_id?: number;
  fichier_drive_id?: string;
  fichier_drive_url?: string;
}

export interface Fournisseur {
  id: string;
  nom: string;
  adresse?: string;
  telephone?: string;
  email?: string;
  siret?: string;
  scope: 'dt' | 'ul';
  scope_id?: string;
}

export interface AuditEntry {
  date: string;
  auteur: string;
  action: string;
  details: string;
  ref: string;
}

export interface DossierListResponse {
  dossiers: DossierReparation[];
  total: number;
}

export interface FournisseurListResponse {
  fournisseurs: Fournisseur[];
  total: number;
}

// Request types

export interface CreateDossierRequest {
  description: string;
  sinistre_ref?: string;
}

export interface UpdateDossierRequest {
  statut?: 'ouvert' | 'cloture' | 'annule';
  description?: string;
}

export interface CreateDevisRequest {
  date_devis: string;
  fournisseur_id: string;
  description_travaux: string;
  montant: number;
}

export interface CreateFactureRequest {
  date_facture: string;
  fournisseur_id: string;
  classification: string;
  description_travaux: string;
  montant_total: number;
  montant_crf: number;
  devis_id?: number;
}

export interface FactureCreateResponse extends Facture {
  warning_no_devis?: boolean;
  warning_ecart?: boolean;
  ecart_pourcentage?: number;
}

export interface CreateFournisseurRequest {
  nom: string;
  adresse?: string;
  telephone?: string;
  email?: string;
  siret?: string;
  scope: 'dt' | 'ul';
  scope_id?: string;
}

export interface UpdateFournisseurRequest {
  nom?: string;
  adresse?: string;
  telephone?: string;
  email?: string;
  siret?: string;
}

// Approbation types

export interface SendApprovalRequest {
  valideur_email: string;
}

export interface SendApprovalResponse {
  token: string;
  valideur_email: string;
  expires_at: string;
  message: string;
}

export interface ApprobationData {
  dt: string;
  immat: string;
  numero_dossier: string;
  devis_id: string;
  devis: Devis;
  dossier_description: string;
  valideur_email: string;
  status: string;
  created_at: string;
  expires_at: string;
}

export interface SubmitDecisionRequest {
  decision: 'approuve' | 'refuse';
  commentaire?: string;
}

export interface SubmitDecisionResponse {
  decision: string;
  message: string;
}

// ========== Dépenses (expenses) ==========

export interface DepenseFacture {
  date: string;
  numero_dossier: string;
  description?: string;
  fournisseur_nom: string;
  classification: string;
  montant_total: number;
  montant_crf: number;
}

export interface DepenseYear {
  year: number;
  nb_dossiers: number;
  total_cout: number;
  total_crf: number;
  factures: DepenseFacture[];
}

export interface DepensesResponse {
  years: DepenseYear[];
  total_all_years_cout: number;
  total_all_years_crf: number;
}
