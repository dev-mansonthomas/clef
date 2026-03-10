/**
 * Configuration models matching backend API
 */

export interface ConfigResponse {
  sheets_url_vehicules: string;
  sheets_url_benevoles: string;
  sheets_url_responsables: string;
  template_doc_url: string;
  email_destinataire_alertes: string;
  email_gestionnaire_dt: string;
}

export interface ConfigUpdate {
  sheets_url_vehicules?: string;
  sheets_url_benevoles?: string;
  sheets_url_responsables?: string;
  template_doc_url?: string;
  email_destinataire_alertes?: string;
}

