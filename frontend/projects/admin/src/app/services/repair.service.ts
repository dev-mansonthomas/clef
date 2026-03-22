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
  FactureCreateResponse,
  AuditEntry,
  SendApprovalRequest,
  SendApprovalResponse,
  BulkApprovalResponse,
  ApprobationData,
  SubmitDecisionRequest,
  SubmitDecisionResponse,
  DepensesResponse,
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

  // ========== Devis ==========

  /**
   * Add a devis to a repair dossier
   */
  createDevis(dt: string, immat: string, numero: string, data: CreateDevisRequest): Observable<Devis> {
    return this.http.post<Devis>(`${this.dossierUrl(dt, immat)}/${numero}/devis`, data, {
      withCredentials: true,
    });
  }

  /**
   * Get a specific devis
   */
  getDevis(dt: string, immat: string, numero: string, devisId: string): Observable<Devis> {
    return this.http.get<Devis>(`${this.dossierUrl(dt, immat)}/${numero}/devis/${devisId}`, {
      withCredentials: true,
    });
  }

  /**
   * Update a devis
   */
  updateDevis(dt: string, immat: string, numero: string, devisId: string, data: Partial<CreateDevisRequest>): Observable<Devis> {
    return this.http.patch<Devis>(`${this.dossierUrl(dt, immat)}/${numero}/devis/${devisId}`, data, {
      withCredentials: true,
    });
  }

  // ========== Factures ==========

  /**
   * Add a facture to a repair dossier
   */
  createFacture(dt: string, immat: string, numero: string, data: CreateFactureRequest): Observable<FactureCreateResponse> {
    return this.http.post<FactureCreateResponse>(`${this.dossierUrl(dt, immat)}/${numero}/factures`, data, {
      withCredentials: true,
    });
  }

  /**
   * Get a specific facture
   */
  getFacture(dt: string, immat: string, numero: string, factureId: string): Observable<Facture> {
    return this.http.get<Facture>(`${this.dossierUrl(dt, immat)}/${numero}/factures/${factureId}`, {
      withCredentials: true,
    });
  }

  // ========== Approbation ==========

  /**
   * Send a devis for approval
   */
  sendApproval(dt: string, immat: string, numero: string, devisId: string, data: SendApprovalRequest): Observable<SendApprovalResponse> {
    return this.http.post<SendApprovalResponse>(
      `${this.dossierUrl(dt, immat)}/${numero}/devis/${devisId}/send-approval`, data, {
        withCredentials: true,
      });
  }

  /**
   * Send all pending devis for approval in one action
   */
  sendBulkApproval(dt: string, immat: string, numero: string, data: { valideur_email: string }): Observable<BulkApprovalResponse> {
    return this.http.post<BulkApprovalResponse>(
      `${this.dossierUrl(dt, immat)}/${numero}/send-bulk-approval`, data, {
        withCredentials: true,
      });
  }

  /**
   * Get approval data (public, no auth)
   */
  getApprobationData(token: string): Observable<ApprobationData> {
    return this.http.get<ApprobationData>(`${this.apiUrl}/api/approbation/${token}`);
  }

  /**
   * Submit approval decision (public, no auth)
   */
  submitDecision(token: string, data: SubmitDecisionRequest): Observable<SubmitDecisionResponse> {
    return this.http.post<SubmitDecisionResponse>(`${this.apiUrl}/api/approbation/${token}`, data);
  }

  // ========== Devis File Upload ==========

  /**
   * Upload or update a file for a devis
   */
  uploadDevisFile(dt: string, immat: string, numero: string, devisId: string, file: File): Observable<Devis> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<Devis>(
      `${this.dossierUrl(dt, immat)}/${numero}/devis/${devisId}/upload`,
      formData,
      { withCredentials: true },
    );
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

  // ========== Dépenses ==========

  /**
   * Get aggregated expenses for a vehicle
   */
  getDepenses(dt: string, immat: string): Observable<DepensesResponse> {
    return this.http.get<DepensesResponse>(`${this.apiUrl}/api/${dt}/vehicles/${immat}/depenses`, {
      withCredentials: true,
    });
  }

  /**
   * Export expenses as CSV or PDF (returns blob for download)
   */
  exportDepenses(dt: string, immat: string, format: 'csv' | 'pdf'): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/api/${dt}/vehicles/${immat}/depenses/export`, {
      params: { format },
      withCredentials: true,
      responseType: 'blob',
    });
  }
}

