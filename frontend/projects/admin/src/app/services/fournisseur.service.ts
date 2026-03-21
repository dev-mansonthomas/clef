import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  Fournisseur,
  FournisseurListResponse,
  CreateFournisseurRequest,
  UpdateFournisseurRequest,
} from '../models/repair.model';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class FournisseurService {
  private readonly apiUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  /**
   * List fournisseurs for a DT (includes DT-level + user's UL-level)
   */
  listFournisseurs(dt: string): Observable<FournisseurListResponse> {
    return this.http.get<FournisseurListResponse>(`${this.apiUrl}/api/${dt}/fournisseurs`, {
      withCredentials: true,
    });
  }

  /**
   * Create a new fournisseur
   */
  createFournisseur(dt: string, data: CreateFournisseurRequest): Observable<Fournisseur> {
    return this.http.post<Fournisseur>(`${this.apiUrl}/api/${dt}/fournisseurs`, data, {
      withCredentials: true,
    });
  }

  /**
   * Update an existing fournisseur
   */
  updateFournisseur(dt: string, id: string, data: UpdateFournisseurRequest): Observable<Fournisseur> {
    return this.http.patch<Fournisseur>(`${this.apiUrl}/api/${dt}/fournisseurs/${id}`, data, {
      withCredentials: true,
    });
  }
}

