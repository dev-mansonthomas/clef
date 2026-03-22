import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  Valideur,
  ValideurListResponse,
  CreateValideurRequest,
  UpdateValideurRequest,
} from '../models/repair.model';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class ValideurService {
  private readonly apiUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  /**
   * List valideurs for a DT (includes DT-level + user's UL-level)
   */
  listValideurs(dt: string): Observable<ValideurListResponse> {
    return this.http.get<ValideurListResponse>(`${this.apiUrl}/api/${dt}/valideurs`, {
      withCredentials: true,
    });
  }

  /**
   * Create a new valideur
   */
  createValideur(dt: string, data: CreateValideurRequest): Observable<Valideur> {
    return this.http.post<Valideur>(`${this.apiUrl}/api/${dt}/valideurs`, data, {
      withCredentials: true,
    });
  }

  /**
   * Update an existing valideur
   */
  updateValideur(dt: string, id: string, data: UpdateValideurRequest): Observable<Valideur> {
    return this.http.patch<Valideur>(`${this.apiUrl}/api/${dt}/valideurs/${id}`, data, {
      withCredentials: true,
    });
  }
}

