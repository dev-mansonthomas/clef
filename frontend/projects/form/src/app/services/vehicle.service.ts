import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Vehicle, VehicleListResponse } from '../models/vehicle.model';

/**
 * Service for vehicle-related API calls
 */
@Injectable({
  providedIn: 'root'
})
export class VehicleService {
  private readonly apiUrl = '/api/vehicles';

  constructor(private http: HttpClient) {}

  /**
   * Get list of all vehicles
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
   * Decode QR code URL to extract vehicle nom_synthetique
   * QR format: https://{DOMAIN}/vehicle/{encoded_id}
   * encoded_id is base64 encoded nom_synthetique
   */
  decodeQrCode(qrCodeUrl: string): string | null {
    try {
      // Extract the encoded ID from the URL
      const urlPattern = /\/vehicle\/([^\/\?]+)/;
      const match = qrCodeUrl.match(urlPattern);
      
      if (!match || !match[1]) {
        console.error('Invalid QR code URL format:', qrCodeUrl);
        return null;
      }

      const encodedId = match[1];
      
      // Decode base64
      const nomSynthetique = atob(encodedId);
      
      return nomSynthetique;
    } catch (error) {
      console.error('Error decoding QR code:', error);
      return null;
    }
  }
}

