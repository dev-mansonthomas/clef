/**
 * Reservation models for calendar events
 */

export interface ReservationCreate {
  indicatif: string;
  chauffeur: string;
  mission: string;
  start: string; // ISO 8601 datetime string
  end: string;   // ISO 8601 datetime string
  description?: string;
}

export interface Reservation {
  id: string;
  indicatif: string;
  chauffeur: string;
  mission: string;
  start: string;
  end: string;
  description?: string;
  color_id?: string;
}

export interface Benevole {
  email: string;
  nom: string;
  prenom: string;
  ul: string;
  nivol: string;
}

