import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router } from '@angular/router';
import { BehaviorSubject } from 'rxjs';
import { vi } from 'vitest';
import { AuthService } from '../../../services/auth.service';
import { User } from '../../../models/user.model';
import { LoginComponent } from './login.component';

/**
 * L'écran de connexion ne doit faire AUCUN appel réseau de son propre chef.
 *
 * Il appelait `getCurrentUser()` dans `ngOnInit`, alors que le constructeur
 * d'`AuthService` (`providedIn: 'root'`) lance déjà un `GET /auth/me` à la première
 * injection — c'est-à-dire ici. La console de l'écran de connexion affichait donc deux
 * 401 et deux erreurs pour une seule information à obtenir.
 *
 * Zéro appel est impossible (cookie de session `HttpOnly`, invisible à JavaScript) :
 * l'objectif est UN appel, celui du service, dont ce composant se contente d'écouter
 * le résultat.
 */
describe('LoginComponent', () => {
  const utilisateur: User = {
    email: 'benevole@croix-rouge.fr',
    nom: 'Dupont',
    prenom: 'Jean',
    dt: 'DT75',
    ul: 'UL Paris 15',
    role: 'Gestionnaire DT',
    perimetre: 'DT Paris',
    type_perimetre: 'DT',
    is_super_admin: false
  };

  const routerMock = { navigate: vi.fn() };

  const monter = (utilisateurCourant: User | null, queryParams: Record<string, string> = {}) => {
    routerMock.navigate.mockReset();
    const currentUser$ = new BehaviorSubject<User | null>(utilisateurCourant);
    const getCurrentUser = vi.fn();

    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        { provide: AuthService, useValue: { currentUser$, getCurrentUser, login: vi.fn() } },
        { provide: Router, useValue: routerMock },
        { provide: ActivatedRoute, useValue: { snapshot: { queryParams } } }
      ]
    });

    const fixture = TestBed.createComponent(LoginComponent);
    fixture.detectChanges();
    return { fixture, currentUser$, getCurrentUser };
  };

  it('ne redemande pas l’utilisateur au serveur', () => {
    const { getCurrentUser } = monter(null);
    expect(getCurrentUser).not.toHaveBeenCalled();
  });

  it('ignore le null initial du BehaviorSubject et reste sur place', () => {
    monter(null);
    expect(routerMock.navigate).not.toHaveBeenCalled();
  });

  it('redirige quand la session arrive après l’affichage', () => {
    const { currentUser$ } = monter(null);
    expect(routerMock.navigate).not.toHaveBeenCalled();

    currentUser$.next(utilisateur);
    expect(routerMock.navigate).toHaveBeenCalledWith(['/dashboard']);
  });

  it('respecte returnUrl', () => {
    const { currentUser$ } = monter(null, { returnUrl: '/approbation/token-123' });
    currentUser$.next(utilisateur);
    expect(routerMock.navigate).toHaveBeenCalledWith(['/approbation/token-123']);
  });

  it('redirige immédiatement un utilisateur déjà connu', () => {
    monter(utilisateur);
    expect(routerMock.navigate).toHaveBeenCalledWith(['/dashboard']);
  });
});
