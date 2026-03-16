import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { UniteLocaleListResponse } from '../models/unite-locale.model';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class UniteLocaleService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;
  private readonly dt = 'DT75'; // TODO: Get from user context

  /**
   * Get list of all Unités Locales for the DT
   */
  getUnitesLocales(): Observable<UniteLocaleListResponse> {
    return this.http.get<UniteLocaleListResponse>(`${this.apiUrl}/api/${this.dt}/unites-locales`);
  }
}

