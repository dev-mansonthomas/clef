import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Vehicle, VehicleUpdate, VehicleListResponse } from '../models/vehicle.model';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class VehicleService {
  private readonly apiUrl = `${environment.apiUrl}/api/vehicles`;

  constructor(private http: HttpClient) {}

  /**
   * Get list of vehicles filtered by user's UL
   */
  getVehicles(): Observable<VehicleListResponse> {
    return this.http.get<VehicleListResponse>(this.apiUrl, { withCredentials: true });
  }

  /**
   * Get a specific vehicle by its synthetic name
   */
  getVehicle(nomSynthetique: string): Observable<Vehicle> {
    return this.http.get<Vehicle>(`${this.apiUrl}/${nomSynthetique}`, { withCredentials: true });
  }

  /**
   * Update vehicle metadata (calendar color, comments, etc.)
   */
  updateVehicle(nomSynthetique: string, update: VehicleUpdate): Observable<Vehicle> {
    return this.http.patch<Vehicle>(`${this.apiUrl}/${nomSynthetique}`, update, { withCredentials: true });
  }

  /**
   * Create a new vehicle
   */
  createVehicle(vehicle: Partial<Vehicle>): Observable<Vehicle> {
    return this.http.post<Vehicle>(this.apiUrl, vehicle, { withCredentials: true });
  }
}

