import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

/**
 * Alert for a vehicle requiring attention
 */
export interface VehicleAlert {
  immatriculation: string;
  marque: string;
  modele: string;
  type: 'ct_expire' | 'ct_bientot' | 'pollution_expire' | 'pollution_bientot';
  date: string;
  jours: number;
}

/**
 * Statistics for a date-based check (CT or pollution)
 */
export interface DateStats {
  en_retard: number;
  dans_2_mois: number;
  ok: number;
}

/**
 * Dashboard statistics response
 */
export interface DashboardStats {
  total_vehicules: number;
  disponibles: number;
  indisponibles: number;
  ct: DateStats;
  pollution: DateStats;
  alertes: VehicleAlert[];
}

@Injectable({
  providedIn: 'root'
})
export class StatsService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;
  private readonly dt = 'DT75'; // TODO: Get from user context

  /**
   * Get dashboard statistics
   */
  getStats(): Observable<DashboardStats> {
    return this.http.get<DashboardStats>(`${this.apiUrl}/api/${this.dt}/stats`);
  }
}

