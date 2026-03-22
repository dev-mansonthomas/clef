/**
 * Configuration models matching backend API
 */

export interface ConfigResponse {
  email_destinataire_alertes: string;
  email_gestionnaire_dt: string;
  drive_folder_id?: string;
  drive_folder_url?: string;
  drive_sync_status: 'idle' | 'in_progress' | 'complete' | 'error';
  drive_sync_processed: number;
  drive_sync_total: number;
  drive_sync_message: string | null;
  drive_sync_error: string | null;
  drive_sync_current_vehicle?: string;
}

export interface ConfigUpdate {
  drive_folder_url?: string;
  email_destinataire_alertes?: string;
}

export interface DocumentFolder {
  name: string;
  mandatory: boolean;
  locked?: boolean;
}

