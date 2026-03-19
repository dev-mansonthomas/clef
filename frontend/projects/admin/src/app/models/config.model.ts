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
  drive_folder_id?: string;
  drive_folder_url?: string;
  drive_sync_status: 'idle' | 'in_progress' | 'complete' | 'error';
  drive_sync_processed: number;
  drive_sync_total: number;
  drive_sync_message: string | null;
  drive_sync_error: string | null;
}

export interface ConfigUpdate {
  sheets_url_vehicules?: string;
  sheets_url_benevoles?: string;
  sheets_url_responsables?: string;
  template_doc_url?: string;
  email_destinataire_alertes?: string;
}

