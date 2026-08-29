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
  // ⚠️ Codé en dur — c'est l'un des quatre services admin dans ce cas (piège 8 du
  // CLAUDE.md). L'application est mono-DT en pratique, alors que le backend est
  // multi-tenant. À prendre du contexte utilisateur le jour où ce n'est plus vrai.
  readonly dt = 'DT75';

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
  /**
   * Base de l'API, telle qu'on la colle dans `CLEF_API_URL` côté Apps Script.
   *
   * ⚠️ Le repli était `https://clef-api.run.app`, une URL qui n'a JAMAIS existé — et
   * comme `environment.apiUrl` est la chaîne vide en production (appels relatifs,
   * proxifiés), c'est ce repli qui s'affichait dans l'écran de configuration. Un
   * opérateur qui le recopiait obtenait des échecs de résolution DNS, à trois niveaux
   * de distance de sa cause.
   *
   * L'origine courante est la bonne réponse : le load balancer route `/api/*` vers
   * l'API, et le relais nginx fait de même par l'URL run.app.
   */
  getBaseUrl(): string {
    return environment.apiUrl || window.location.origin;
  }

  /**
   * Les trois flux de synchronisation, tels que les scripts les appellent.
   *
   * ⚠️ Ce ne sont PAS des valeurs à recopier dans les propriétés du script : chaque
   * script construit son chemin lui-même, à partir de `CLEF_API_URL` et de `CLEF_DT`.
   * L'écran n'affichait qu'un seul de ces chemins, complet, sous le titre « URL de
   * synchronisation » — collé dans `CLEF_API_URL`, il produisait
   * `…/api/sync/DT75/vehicules/api/sync/DT75/benevoles`. Ils sont ici pour vérifier
   * et diagnostiquer, pas pour être collés.
   */
  getFluxSynchronisation(): Array<{
    classeur: string; script: string; methode: string; url: string; sens: string;
  }> {
    const base = this.getBaseUrl();
    return [
      {
        classeur: 'Référentiel Véhicules',
        script: 'sync-referentiel.gs',
        methode: 'GET',
        url: `${base}/api/sync/${this.dt}/vehicules`,
        sens: 'CLEF → feuille'
      },
      {
        classeur: 'Référentiel Véhicules',
        script: 'sync-responsables.gs',
        methode: 'GET',
        url: `${base}/api/sync/${this.dt}/responsables`,
        sens: 'CLEF → feuille'
      },
      {
        classeur: 'CLEF Benevoles',
        script: 'sync-benevoles.gs',
        methode: 'POST',
        url: `${base}/api/sync/${this.dt}/benevoles`,
        sens: 'feuille → CLEF'
      }
    ];
  }

  getSyncUrlDT(): string {
    return `${this.getBaseUrl()}/api/sync/${this.dt}/vehicules`;
  }

  getSyncUrlUL(ulId: string): string {
    return `${this.getBaseUrl()}/api/sync/${this.dt}/vehicules/${ulId}`;
  }
}

