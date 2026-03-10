import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  RetourVehiculeRequest,
  RetourVehiculeResponse,
  PriseVehiculeData,
  PriseVehiculeRequest,
  PriseVehiculeResponse
} from '../models/carnet-bord.model';

@Injectable({
  providedIn: 'root'
})
export class CarnetBordService {
  private readonly apiUrl = '/api/carnet-de-bord';

  constructor(private http: HttpClient) {}

  /**
   * Submit vehicle pickup form
   */
  submitPrise(prise: PriseVehiculeRequest): Observable<PriseVehiculeResponse> {
    return this.http.post<PriseVehiculeResponse>(`${this.apiUrl}/prise`, prise);
  }

  /**
   * Submit vehicle return form
   */
  submitRetour(retour: RetourVehiculeRequest): Observable<RetourVehiculeResponse> {
    return this.http.post<RetourVehiculeResponse>(`${this.apiUrl}/retour`, retour);
  }

  /**
   * Get recent pickup data for a vehicle to calculate km traveled
   */
  getRecentPrise(vehiculeId: string): Observable<PriseVehiculeData | null> {
    return this.http.get<PriseVehiculeData | null>(
      `${this.apiUrl}/${vehiculeId}/derniere-prise`
    );
  }

  /**
   * Upload photos for vehicle pickup
   */
  uploadPhotosPrise(nomSynthetique: string, photos: File[]): Observable<{ urls: string[] }> {
    const formData = new FormData();
    photos.forEach((photo, index) => {
      formData.append(`photo_${index}`, photo);
    });

    return this.http.post<{ urls: string[] }>(
      `${this.apiUrl}/prise/${nomSynthetique}/photos`,
      formData
    );
  }

  /**
   * Upload photos for vehicle return
   */
  uploadPhotos(nomSynthetique: string, photos: File[]): Observable<{ urls: string[] }> {
    const formData = new FormData();
    photos.forEach((photo, index) => {
      formData.append(`photo_${index}`, photo);
    });

    return this.http.post<{ urls: string[] }>(
      `${this.apiUrl}/retour/${nomSynthetique}/photos`,
      formData
    );
  }
}

