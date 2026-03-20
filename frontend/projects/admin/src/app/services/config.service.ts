import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ConfigResponse, ConfigUpdate, DocumentFolder } from '../models/config.model';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class ConfigService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  getConfig(): Observable<ConfigResponse> {
    return this.http.get<ConfigResponse>(`${this.apiUrl}/api/config`);
  }

  updateConfig(updates: ConfigUpdate): Observable<ConfigResponse> {
    return this.http.patch<ConfigResponse>(`${this.apiUrl}/api/config`, updates);
  }

  resetDriveSync(): Observable<{message: string}> {
    return this.http.delete<{message: string}>(`${this.apiUrl}/api/config/drive-sync`);
  }

  cancelDriveSync(): Observable<{message: string}> {
    return this.http.post<{message: string}>(`${this.apiUrl}/api/config/drive-sync/cancel`, {});
  }

  restartDriveSync(): Observable<any> {
    return this.http.post(`${this.apiUrl}/api/config/drive-sync/restart`, {});
  }

  getDocumentFolders(): Observable<DocumentFolder[]> {
    return this.http.get<DocumentFolder[]>(`${this.apiUrl}/api/config/document-folders`);
  }

  saveDocumentFolders(folders: DocumentFolder[]): Observable<DocumentFolder[]> {
    return this.http.put<DocumentFolder[]>(`${this.apiUrl}/api/config/document-folders`, { folders });
  }

  syncDocumentFolders(folders: DocumentFolder[]): Observable<ConfigResponse> {
    return this.http.post<ConfigResponse>(`${this.apiUrl}/api/config/document-folders/sync`, { folders });
  }
}

