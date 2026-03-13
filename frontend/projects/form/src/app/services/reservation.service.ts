import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import {
  ValkeyReservation,
  ValkeyReservationCreate,
  ValkeyReservationListResponse,
  Benevole
} from '../models/reservation.model';

/**
 * Service for managing vehicle reservations
 */
@Injectable({
  providedIn: 'root'
})
export class ReservationService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl || 'http://localhost:8000';

  /**
   * Get list of reservations for a DT
   * @param dt Délégation Territoriale code (e.g., "DT75")
   * @param view View mode: 'ul' for user's UL only, 'dt' for all DT
   * @param fromDate Optional start date filter
   * @param toDate Optional end date filter
   * @param vehiculeImmat Optional vehicle filter
   */
  getReservations(
    dt: string,
    view: 'ul' | 'dt' = 'ul',
    fromDate?: string,
    toDate?: string,
    vehiculeImmat?: string
  ): Observable<ValkeyReservationListResponse> {
    let params = new HttpParams();
    
    if (fromDate) {
      params = params.set('from', fromDate);
    }
    if (toDate) {
      params = params.set('to', toDate);
    }
    if (vehiculeImmat) {
      params = params.set('vehicule_immat', vehiculeImmat);
    }

    return this.http.get<ValkeyReservationListResponse>(
      `${this.apiUrl}/api/calendar/${dt}/reservations`,
      { params }
    );
  }

  /**
   * Get a single reservation by ID
   * @param dt Délégation Territoriale code
   * @param id Reservation ID
   */
  getReservation(dt: string, id: string): Observable<ValkeyReservation> {
    return this.http.get<ValkeyReservation>(
      `${this.apiUrl}/api/calendar/${dt}/reservations/${id}`
    );
  }

  /**
   * Create a new reservation
   * @param dt Délégation Territoriale code
   * @param data Reservation data
   */
  createReservation(
    dt: string,
    data: ValkeyReservationCreate
  ): Observable<ValkeyReservation> {
    return this.http.post<ValkeyReservation>(
      `${this.apiUrl}/api/calendar/${dt}/reservations`,
      data
    );
  }

  /**
   * Update an existing reservation
   * @param dt Délégation Territoriale code
   * @param id Reservation ID
   * @param data Updated reservation data
   */
  updateReservation(
    dt: string,
    id: string,
    data: ValkeyReservationCreate
  ): Observable<ValkeyReservation> {
    return this.http.put<ValkeyReservation>(
      `${this.apiUrl}/api/calendar/${dt}/reservations/${id}`,
      data
    );
  }

  /**
   * Delete a reservation
   * @param dt Délégation Territoriale code
   * @param id Reservation ID
   */
  deleteReservation(dt: string, id: string): Observable<void> {
    return this.http.delete<void>(
      `${this.apiUrl}/api/calendar/${dt}/reservations/${id}`
    );
  }

  /**
   * Check if user can edit a reservation
   * @param reservation The reservation to check
   * @param currentUserEmail Current user's email
   */
  canEdit(reservation: ValkeyReservation, currentUserEmail: string): boolean {
    return reservation.created_by === currentUserEmail;
  }

  /**
   * Check if user can delete a reservation
   * @param reservation The reservation to check
   * @param currentUserEmail Current user's email
   */
  canDelete(reservation: ValkeyReservation, currentUserEmail: string): boolean {
    return reservation.created_by === currentUserEmail;
  }

  /**
   * Get list of benevoles (volunteers)
   */
  getBenevoles(): Observable<{ count: number; benevoles: Benevole[] }> {
    return this.http.get<{ count: number; benevoles: Benevole[] }>(
      `${this.apiUrl}/api/benevoles`
    );
  }
}

