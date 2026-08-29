import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ApiKeysService } from './api-keys.service';

/**
 * L'écran de configuration affichait une URL de synchronisation inutilisable.
 *
 * Deux défauts, constatés le 2026-08-29 :
 *
 * 1. `environment.apiUrl` est la chaîne vide en production — les appels sont relatifs
 *    et proxifiés — donc le repli s'appliquait : `https://clef-api.run.app`, une URL
 *    qui n'a JAMAIS existé. Un opérateur qui la recopiait obtenait un échec DNS, à
 *    trois niveaux de distance de sa cause.
 * 2. Elle était présentée sous le titre « URL de synchronisation » alors qu'elle ne
 *    correspond à aucune propriété de script : `CLEF_API_URL` attend la BASE, chaque
 *    script y ajoutant son chemin. Collée telle quelle, elle produisait
 *    `…/api/sync/DT75/vehicules/api/sync/DT75/benevoles`.
 *
 * Et les flux bénévoles et responsables n'apparaissaient nulle part, faute de place
 * pour une seule URL — alors qu'il y en a trois.
 */
describe('ApiKeysService — ce qu’affiche l’écran de configuration', () => {
  let service: ApiKeysService;

  beforeEach(() => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()]
    });
    service = TestBed.inject(ApiKeysService);
  });

  it('donne l’origine courante comme base, pas un domaine inventé', () => {
    expect(service.getBaseUrl()).toBe(window.location.origin);
    expect(service.getBaseUrl()).not.toContain('clef-api.run.app');
  });

  it('décrit les TROIS flux, avec leur méthode et leur sens', () => {
    const flux = service.getFluxSynchronisation();
    expect(flux.length).toBe(3);

    const parScript = new Map(flux.map(f => [f.script, f]));

    // Les deux flux descendants vivent dans le classeur des véhicules.
    expect(parScript.get('sync-referentiel.gs')!.methode).toBe('GET');
    expect(parScript.get('sync-referentiel.gs')!.url)
      .toBe(`${window.location.origin}/api/sync/DT75/vehicules`);
    expect(parScript.get('sync-responsables.gs')!.url)
      .toBe(`${window.location.origin}/api/sync/DT75/responsables`);

    // Le flux montant, lui, vit dans « CLEF Benevoles » — et c'est un POST.
    const benevoles = parScript.get('sync-benevoles.gs')!;
    expect(benevoles.methode).toBe('POST');
    expect(benevoles.classeur).toBe('CLEF Benevoles');
    expect(benevoles.sens).toBe('feuille → CLEF');
    expect(benevoles.url).toBe(`${window.location.origin}/api/sync/DT75/benevoles`);
  });

  it('n’expose aucun chemin absolu comme valeur à coller', () => {
    // La base ne doit PAS porter de chemin : c'est tout le défaut d'origine.
    expect(service.getBaseUrl()).not.toContain('/api/');
  });
});
