import { APP_BASE_HREF } from '@angular/common';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { vi } from 'vitest';
import { AuthService } from './auth.service';

/**
 * L'URL de retour envoyée à Google doit porter le SOUS-CHEMIN de l'application.
 *
 * Les deux applications sont servies sous un préfixe (`/admin/`, `/form/`), et le
 * `returnUrl` posé par le guard est une route Angular — « /dashboard ». Concaténé à
 * `window.location.origin`, il donnait `https://dev.clef.paquerette.com/dashboard` :
 * nginx répondait 404 après une authentification pourtant réussie. Constaté sur le
 * premier déploiement du domaine, le 2026-08-29.
 *
 * Le symptôme est trompeur — « l'authentification ne marche pas » — alors que tout le
 * parcours OAuth avait fonctionné. D'où ce test, qui fixe la construction de l'URL.
 */
describe('AuthService.login', () => {
  const monter = (baseHref: string) => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: APP_BASE_HREF, useValue: baseHref },
        { provide: Router, useValue: { navigate: vi.fn() } }
      ]
    });
    const service = TestBed.inject(AuthService);
    const httpMock = TestBed.inject(HttpTestingController);
    // Le constructeur du service appelle /auth/me : le vider pour n'observer que /auth/login.
    httpMock.match(r => r.url.endsWith('/auth/me')).forEach(r => r.flush(null, {
      status: 401, statusText: 'Unauthorized'
    }));
    return { service, httpMock };
  };

  const redirectToEnvoye = (baseHref: string, returnUrl?: string): string => {
    const { service, httpMock } = monter(baseHref);
    service.login(returnUrl);
    const requete = httpMock.expectOne(r => r.url.endsWith('/auth/login'));
    const valeur = requete.request.params.get('redirect_to')!;
    requete.flush({ authorization_url: 'https://accounts.google.com/o/oauth2/v2/auth' });
    return valeur;
  };

  it('préfixe le returnUrl du base href de l’application', () => {
    expect(redirectToEnvoye('/admin/', '/dashboard'))
      .toBe(`${window.location.origin}/admin/dashboard`);
  });

  it('renvoie à la racine de l’APPLICATION quand aucun returnUrl n’est donné', () => {
    // Et non à la racine du domaine, qui sert la page de choix d'application.
    expect(redirectToEnvoye('/admin/')).toBe(`${window.location.origin}/admin/`);
  });

  it('reste correct en développement local, servi à la racine', () => {
    expect(redirectToEnvoye('/', '/dashboard'))
      .toBe(`${window.location.origin}/dashboard`);
  });

  it('conserve un chemin profond, comme un lien d’approbation', () => {
    expect(redirectToEnvoye('/admin/', '/approbation/token-123'))
      .toBe(`${window.location.origin}/admin/approbation/token-123`);
  });
});
