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
  telephone: string | null;
  nivol: string | null;
  /**
   * Organisation détenue par CLEF — pas par la feuille de référentiel.
   *
   * Le champ `role` à valeur unique a disparu : il ne pouvait pas exprimer qu'un
   * bénévole est responsable de son UL **et** porteur d'une fonction à la DT.
   * Voir docs/specs/synchronisation-referentiel-benevoles.md.
   */
  responsable_ul: boolean;
  fonctions_dt: string[];
}

/**
 * Response for list of bénévoles
 */
export interface BenevoleListResponse {
  count: number;
  benevoles: Benevole[];
}

/**
 * Mise à jour partielle de l'organisation d'un bénévole.
 *
 * Ne porte que des champs détenus par CLEF : l'identité (nom, prénom, UL, email,
 * téléphone) vient de la feuille et serait de toute façon réécrite à la
 * synchronisation suivante. Un champ omis n'est pas modifié.
 */
export interface BenevoleOrganisationUpdate {
  responsable_ul?: boolean;
  fonctions_dt?: string[];
  statut?: 'actif' | 'inactif';
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
   * Met à jour l'organisation d'un bénévole (responsabilité d'UL, fonctions DT, statut)
   */
  updateBenevoleOrganisation(
    dt: string,
    email: string,
    update: BenevoleOrganisationUpdate
  ): Observable<Benevole> {
    return this.http.patch<Benevole>(
      `${this.apiUrl}/${dt}/benevoles/${encodeURIComponent(email)}`,
      update
    );
  }
}

