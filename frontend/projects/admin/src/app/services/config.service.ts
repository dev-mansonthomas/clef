import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ConfigResponse, ConfigUpdate } from '../models/config.model';
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
}

