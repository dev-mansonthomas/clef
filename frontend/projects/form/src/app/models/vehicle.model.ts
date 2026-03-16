/**
 * Vehicle model for form app
 * Simplified version focusing on fields needed for vehicle selection
 */

export type DisponibiliteStatus = 'Dispo' | 'Indispo';

export interface Vehicle {
  dt_ul: string;
  immat: string;
  indicatif: string;
  operationnel_mecanique: DisponibiliteStatus;
  marque: string;
  modele: string;
  type: string;
  nom_synthetique: string;
  lieu_stationnement: string;
}

export interface VehicleListResponse {
  count: number;
  vehicles: Vehicle[];
}

