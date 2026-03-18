import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  ManagedVehicleDocumentType,
  Vehicle,
  VehicleDriveDocument,
  VehicleDriveDocumentsResponse,
  VehicleDriveFileListResponse,
  VehicleListResponse,
  VehicleUpdate,
} from '../models/vehicle.model';
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
   * Get the Google Drive document overview for a vehicle.
   */
  getVehicleDriveDocuments(nomSynthetique: string): Observable<VehicleDriveDocumentsResponse> {
    return this.http.get<VehicleDriveDocumentsResponse>(`${this.apiUrl}/${nomSynthetique}/drive-documents`, {
      withCredentials: true,
    });
  }

  /**
   * List existing files in a managed Drive subfolder.
   */
  listVehicleDriveDocumentFiles(
    nomSynthetique: string,
    documentType: ManagedVehicleDocumentType,
  ): Observable<VehicleDriveFileListResponse> {
    return this.http.get<VehicleDriveFileListResponse>(
      `${this.apiUrl}/${nomSynthetique}/drive-documents/${documentType}/files`,
      { withCredentials: true },
    );
  }

  /**
   * Associate an existing Drive file to the vehicle.
   */
  selectVehicleDriveDocument(
    nomSynthetique: string,
    documentType: ManagedVehicleDocumentType,
    fileId: string,
  ): Observable<VehicleDriveDocument> {
    return this.http.post<VehicleDriveDocument>(
      `${this.apiUrl}/${nomSynthetique}/drive-documents/${documentType}/select`,
      { file_id: fileId },
      { withCredentials: true },
    );
  }

  /**
   * Upload a new Drive file and select it as current document.
   */
  uploadVehicleDriveDocument(
    nomSynthetique: string,
    documentType: ManagedVehicleDocumentType,
    file: File,
  ): Observable<VehicleDriveDocument> {
    const formData = new FormData();
    formData.append('file', file);

    return this.http.post<VehicleDriveDocument>(
      `${this.apiUrl}/${nomSynthetique}/drive-documents/${documentType}/upload`,
      formData,
      { withCredentials: true },
    );
  }

  /**
   * Create a new vehicle
   */
  createVehicle(vehicle: Partial<Vehicle>): Observable<Vehicle> {
    return this.http.post<Vehicle>(this.apiUrl, vehicle, { withCredentials: true });
  }
}

