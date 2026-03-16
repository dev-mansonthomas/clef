import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ApiKey, ApiKeyCreate } from '../models/api-key.model';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class ApiKeysService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;
  private readonly dt = 'DT75'; // TODO: Get from user context

  // DT-level API keys
  listApiKeysDT(): Observable<ApiKey[]> {
    return this.http.get<ApiKey[]>(`${this.apiUrl}/api/${this.dt}/config/api-keys`);
  }

  createApiKeyDT(data: ApiKeyCreate): Observable<ApiKey> {
    return this.http.post<ApiKey>(`${this.apiUrl}/api/${this.dt}/config/api-keys`, data);
  }

  deleteApiKeyDT(keyId: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/api/${this.dt}/config/api-keys/${keyId}`);
  }

  // UL-level API keys
  listApiKeysUL(ulId: string): Observable<ApiKey[]> {
    return this.http.get<ApiKey[]>(`${this.apiUrl}/api/${this.dt}/unites-locales/${ulId}/api-keys`);
  }

  createApiKeyUL(ulId: string, data: ApiKeyCreate): Observable<ApiKey> {
    return this.http.post<ApiKey>(`${this.apiUrl}/api/${this.dt}/unites-locales/${ulId}/api-keys`, data);
  }

  deleteApiKeyUL(ulId: string, keyId: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/api/${this.dt}/unites-locales/${ulId}/api-keys/${keyId}`);
  }

  // Helper to get sync URL
  getSyncUrlDT(): string {
    const baseUrl = environment.apiUrl || 'https://clef-api.run.app';
    return `${baseUrl}/api/sync/${this.dt}/vehicules`;
  }

  getSyncUrlUL(ulId: string): string {
    const baseUrl = environment.apiUrl || 'https://clef-api.run.app';
    return `${baseUrl}/api/sync/${this.dt}/vehicules/${ulId}`;
  }
}

