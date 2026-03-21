import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  DossierReparation,
  DossierListResponse,
  CreateDossierRequest,
  UpdateDossierRequest,
  Devis,
  CreateDevisRequest,
  Facture,
  CreateFactureRequest,
  AuditEntry,
} from '../models/repair.model';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class RepairService {
  private readonly apiUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  private dossierUrl(dt: string, immat: string): string {
    return `${this.apiUrl}/api/${dt}/vehicles/${immat}/dossiers-reparation`;
  }

  // ========== Dossiers ==========

  /**
   * List all repair dossiers for a vehicle
   */
  listDossiers(dt: string, immat: string): Observable<DossierListResponse> {
    return this.http.get<DossierListResponse>(this.dossierUrl(dt, immat), {
      withCredentials: true,
    });
  }

  /**
   * Get a specific repair dossier
   */
  getDossier(dt: string, immat: string, numero: string): Observable<DossierReparation> {
    return this.http.get<DossierReparation>(`${this.dossierUrl(dt, immat)}/${numero}`, {
      withCredentials: true,
    });
  }

  /**
   * Create a new repair dossier
   */
  createDossier(dt: string, immat: string, data: CreateDossierRequest): Observable<DossierReparation> {
    return this.http.post<DossierReparation>(this.dossierUrl(dt, immat), data, {
      withCredentials: true,
    });
  }

  /**
   * Update a repair dossier (e.g. close, reopen)
   */
  updateDossier(dt: string, immat: string, numero: string, data: UpdateDossierRequest): Observable<DossierReparation> {
    return this.http.patch<DossierReparation>(`${this.dossierUrl(dt, immat)}/${numero}`, data, {
      withCredentials: true,
    });
  }

  // ========== Devis (will be used in Wave 3) ==========

  /**
   * Add a devis to a repair dossier
   */
  createDevis(dt: string, immat: string, numero: string, data: CreateDevisRequest): Observable<Devis> {
    return this.http.post<Devis>(`${this.dossierUrl(dt, immat)}/${numero}/devis`, data, {
      withCredentials: true,
    });
  }

  // ========== Factures (will be used in Wave 3) ==========

  /**
   * Add a facture to a repair dossier
   */
  createFacture(dt: string, immat: string, numero: string, data: CreateFactureRequest): Observable<Facture> {
    return this.http.post<Facture>(`${this.dossierUrl(dt, immat)}/${numero}/factures`, data, {
      withCredentials: true,
    });
  }

  // ========== Historique ==========

  /**
   * Get audit history for a repair dossier
   */
  getHistorique(dt: string, immat: string, numero: string): Observable<AuditEntry[]> {
    return this.http.get<AuditEntry[]>(`${this.dossierUrl(dt, immat)}/${numero}/historique`, {
      withCredentials: true,
    });
  }
}

