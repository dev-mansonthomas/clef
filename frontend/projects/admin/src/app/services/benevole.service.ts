import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

/**
 * Bénévole model
 */
export interface Benevole {
  email: string;
  nom: string;
  prenom: string;
  ul: string | null;
  role: string | null;
  nivol: string | null;
}

/**
 * Response for list of bénévoles
 */
export interface BenevoleListResponse {
  count: number;
  benevoles: Benevole[];
}

/**
 * Request for updating bénévole role
 */
export interface BenevoleRoleUpdate {
  role: string | null;
  ul?: string | null;
}

/**
 * Service for managing bénévoles
 */
@Injectable({
  providedIn: 'root'
})
export class BenevoleService {
  private readonly apiUrl = `${environment.apiUrl}/api`;

  constructor(private http: HttpClient) {}

  /**
   * Get list of all bénévoles for a DT
   */
  getBenevoles(dt: string): Observable<BenevoleListResponse> {
    return this.http.get<BenevoleListResponse>(`${this.apiUrl}/${dt}/benevoles`);
  }

  /**
   * Update a bénévole's role
   */
  updateBenevoleRole(dt: string, email: string, roleUpdate: BenevoleRoleUpdate): Observable<Benevole> {
    return this.http.patch<Benevole>(`${this.apiUrl}/${dt}/benevoles/${email}`, roleUpdate);
  }
}

