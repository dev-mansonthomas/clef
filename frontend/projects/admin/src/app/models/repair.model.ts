/**
 * Repair dossier models matching backend API structure
 */

export interface FichierDrive {
  file_id: string;
  name: string;
  web_view_link: string;
}

export interface FournisseurSnapshot {
  id: string;
  nom: string;
  adresse?: string;
  telephone?: string;
  siret?: string;
  email?: string;
  numero_contrat?: string;
}

export interface DossierReparation {
  numero: string;  // REP-2026-001
  immat: string;
  dt: string;
  titre?: string;
  description: string[];
  commentaire?: string;
  statut: 'ouvert' | 'cloture' | 'annule';
  cree_par: string;
  cree_le: string;
  cloture_le?: string;
  photos?: FichierDrive[];
  sinistre_id?: string;
  devis: Devis[];
  factures: Facture[];
}

export interface Devis {
  id: string;
  date_devis: string;
  fournisseur: FournisseurSnapshot;
  description?: string;
  description_items?: string[];
  description_travaux?: string;
  montant: number;
  statut: 'en_attente' | 'envoye' | 'approuve' | 'refuse' | 'annule';
  fichier?: FichierDrive;
  valideur_email?: string;
  valideur_commentaire?: string;
  date_envoi_approbation?: string;
  date_decision?: string;
  cree_par: string;
  cree_le: string;
}

export interface Facture {
  id: string;
  date_facture: string;
  fournisseur: FournisseurSnapshot;
  classification: string;
  description?: string;
  description_items?: string[];
  montant_total: number;
  montant_crf: number;
  fichier?: FichierDrive;
  devis_id?: string;
  cree_par: string;
  cree_le: string;
}

export interface Fournisseur {
  id: string;
  nom: string;
  adresse?: string;
  telephone?: string;
  email?: string;
  siret?: string;
  contact_nom?: string;
  specialites: string[];
  niveau: 'dt' | 'ul';
  ul_id?: string;
  adresse_rue?: string;
  adresse_code_postal?: string;
  adresse_ville?: string;
  numero_contrat?: string;
  archive: boolean;
  cree_par: string;
  cree_le: string;
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
  count: number;
}

export interface FournisseurListResponse {
  fournisseurs: Fournisseur[];
  count: number;
}

// Request types

export interface CreateDossierRequest {
  titre?: string;
  description: string[];
  commentaire?: string;
  sinistre_ref?: string;
}

export interface UpdateDossierRequest {
  titre?: string;
  statut?: 'ouvert' | 'cloture' | 'annule';
  description?: string[];
  commentaire?: string;
}

export interface CreateDevisRequest {
  date_devis: string;
  fournisseur_id: string;
  fournisseur_nom: string;
  description_travaux?: string;
  description_items?: string[];
  montant: number;
}

export interface CreateFactureRequest {
  date_facture: string;
  fournisseur_id: string;
  fournisseur_nom: string;
  classification: string;
  description_travaux: string;
  description_items?: string[];
  montant_total: number;
  montant_crf: number;
  devis_id?: string;
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
  contact_nom?: string;
  specialites?: string[];
  niveau: 'dt' | 'ul';
  ul_id?: string;
  adresse_rue?: string;
  adresse_code_postal?: string;
  adresse_ville?: string;
  numero_contrat?: string;
}

export interface UpdateFournisseurRequest {
  nom?: string;
  adresse?: string;
  telephone?: string;
  email?: string;
  siret?: string;
  contact_nom?: string;
  specialites?: string[];
  adresse_rue?: string;
  adresse_code_postal?: string;
  adresse_ville?: string;
  numero_contrat?: string;
  archive?: boolean;
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
  dossier_description: string[];
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

export interface BulkApprovalResponse {
  count: number;
  tokens: string[];
  valideur_email: string;
  message: string;
}

// ========== Valideurs (approvers) ==========

export interface Valideur {
  id: string;
  prenom: string;
  nom: string;
  email: string;
  role?: string;
  actif: boolean;
  cree_par: string;
  cree_le: string;
}

export interface ValideurListResponse {
  count: number;
  valideurs: Valideur[];
}

export interface CreateValideurRequest {
  prenom: string;
  nom: string;
  email: string;
  role?: string;
  niveau: 'dt' | 'ul';
}

export interface UpdateValideurRequest {
  prenom?: string;
  nom?: string;
  email?: string;
  role?: string;
  actif?: boolean;
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
