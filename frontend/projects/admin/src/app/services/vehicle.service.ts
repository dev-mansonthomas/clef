import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Vehicle, VehicleUpdate, VehicleListResponse } from '../models/vehicle.model';

@Injectable({
  providedIn: 'root'
})
export class VehicleService {
  private readonly apiUrl = '/api/vehicles';

  constructor(private http: HttpClient) {}

  /**
   * Get list of vehicles filtered by user's UL
   */
  getVehicles(): Observable<VehicleListResponse> {
    return this.http.get<VehicleListResponse>(this.apiUrl);
  }

  /**
   * Get a specific vehicle by its synthetic name
   */
  getVehicle(nomSynthetique: string): Observable<Vehicle> {
    return this.http.get<Vehicle>(`${this.apiUrl}/${nomSynthetique}`);
  }

  /**
   * Update vehicle metadata (calendar color, comments, etc.)
   */
  updateVehicle(nomSynthetique: string, update: VehicleUpdate): Observable<Vehicle> {
    return this.http.patch<Vehicle>(`${this.apiUrl}/${nomSynthetique}`, update);
  }
}

