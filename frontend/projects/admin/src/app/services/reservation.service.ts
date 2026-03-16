import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Reservation, ReservationCreate, Benevole } from '../models/reservation.model';
import { VehicleListResponse } from '../models/vehicle.model';

@Injectable({
  providedIn: 'root'
})
export class ReservationService {
  private readonly apiUrl = '/api/reservations';
  private readonly vehiclesUrl = '/api/vehicles';
  private readonly benevolesUrl = '/api/benevoles';

  constructor(private http: HttpClient) {}

  /**
   * Create a new reservation
   */
  createReservation(reservation: ReservationCreate): Observable<Reservation> {
    return this.http.post<Reservation>(this.apiUrl, reservation);
  }

  /**
   * Get available vehicles for a time period
   */
  getAvailableVehicles(start: string, end: string): Observable<VehicleListResponse> {
    return this.http.get<VehicleListResponse>(`${this.vehiclesUrl}/available`, {
      params: { start, end }
    });
  }

  /**
   * Get all benevoles for autocomplete
   */
  getBenevoles(): Observable<{ count: number; benevoles: Benevole[] }> {
    return this.http.get<{ count: number; benevoles: Benevole[] }>(this.benevolesUrl);
  }
}

