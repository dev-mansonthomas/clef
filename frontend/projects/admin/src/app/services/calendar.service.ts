import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface ValkeyReservation {
  id: string;
  vehicule_immat: string;
  chauffeur_nivol: string;
  chauffeur_nom: string;
  mission: string;
  debut: string; // ISO 8601 datetime
  fin: string;   // ISO 8601 datetime
  lieu_depart?: string;
  commentaire?: string;
  created_by: string;
  created_at: string;
}

export interface ValkeyReservationListResponse {
  count: number;
  reservations: ValkeyReservation[];
}

@Injectable({
  providedIn: 'root'
})
export class CalendarService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  /**
   * Get reservations for a DT
   */
  getReservations(dt: string, fromDate?: string, toDate?: string): Observable<ValkeyReservationListResponse> {
    let url = `${this.apiUrl}/api/calendar/${dt}/reservations`;
    const params: any = {};

    if (fromDate) {
      params.from = fromDate;
    }
    if (toDate) {
      params.to = toDate;
    }

    return this.http.get<ValkeyReservationListResponse>(url, { params });
  }

  /**
   * Get iCal feed URL for a DT
   */
  getICalFeedUrl(dt: string): string {
    return `${this.apiUrl}/api/calendar/${dt}/reservations.ics`;
  }
}

