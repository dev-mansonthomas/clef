/**
 * Reservation models for Valkey-based reservations
 */

export interface ValkeyReservationCreate {
  vehicule_immat: string;
  chauffeur_nivol: string;
  chauffeur_nom: string;
  mission: string;
  debut: string; // ISO 8601 datetime string
  fin: string;   // ISO 8601 datetime string
  lieu_depart?: string;
  commentaire?: string;
}

export interface ValkeyReservation extends ValkeyReservationCreate {
  id: string;
  created_by: string;
  created_at: string; // ISO 8601 datetime string
}

export interface ValkeyReservationListResponse {
  count: number;
  reservations: ValkeyReservation[];
}

export interface Benevole {
  email: string;
  nom: string;
  prenom: string;
  ul: string;
  nivol: string;
}

