import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { UniteLocale, UniteLocaleListResponse, UniteLocaleCreate, UniteLocaleUpdate } from '../models/unite-locale.model';
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

  /**
   * Create a new Unité Locale
   */
  createUniteLocale(ul: UniteLocaleCreate): Observable<UniteLocale> {
    return this.http.post<UniteLocale>(`${this.apiUrl}/api/${this.dt}/unites-locales`, ul);
  }

  /**
   * Update an existing Unité Locale
   */
  updateUniteLocale(ulId: string, ul: UniteLocaleUpdate): Observable<UniteLocale> {
    return this.http.put<UniteLocale>(`${this.apiUrl}/api/${this.dt}/unites-locales/${ulId}`, ul);
  }

  /**
   * Delete an Unité Locale
   */
  deleteUniteLocale(ulId: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/api/${this.dt}/unites-locales/${ulId}`);
  }
}

