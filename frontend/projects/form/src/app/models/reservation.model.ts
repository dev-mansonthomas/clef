/**
 * Reservation models for Redis-based reservations
 */

export interface RedisReservationCreate {
  vehicule_immat: string;
  chauffeur_nivol: string;
  chauffeur_nom: string;
  mission: string;
  debut: string; // ISO 8601 datetime string
  fin: string;   // ISO 8601 datetime string
  lieu_depart?: string;
  commentaire?: string;
}

export interface RedisReservation extends RedisReservationCreate {
  id: string;
  created_by: string;
  created_at: string; // ISO 8601 datetime string
}

export interface RedisReservationListResponse {
  count: number;
  reservations: RedisReservation[];
}

export interface Benevole {
  email: string;
  nom: string;
  prenom: string;
  ul: string;
  nivol: string;
}

