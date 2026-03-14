/**
 * API Key models matching backend API
 */

export interface ApiKey {
  id: string;
  name: string;
  key: string;
  created_at: string;
  created_by: string;
  last_used: string | null;
}

export interface ApiKeyCreate {
  key_type: string;
}

