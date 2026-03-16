/**
 * Unité Locale models matching backend API
 */

export interface UniteLocale {
  id: string;
  nom: string;
  dt: string;
  created_at?: string;
}

export interface UniteLocaleListResponse {
  unites_locales: UniteLocale[];
  total: number;
}

export interface UniteLocaleCreate {
  id: string;
  nom: string;
  dt: string;
}

export interface UniteLocaleUpdate {
  nom: string;
}

