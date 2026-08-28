import { Component, DestroyRef, inject, OnInit } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { filter, take } from 'rxjs/operators';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { AuthService } from '../../../services/auth.service';
import { environnementCourant } from '../../../core/environnement';

/**
 * Login component handling Okta authentication
 */
@Component({
  selector: 'app-login',
  standalone: true,
  imports: [MatButtonModule, MatCardModule],
  templateUrl: './login.component.html',
  styleUrl: './login.component.scss'
})
export class LoginComponent implements OnInit {
  private readonly authService = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  /**
   * Environnement servi par cette page, déduit du nom d'hôte.
   *
   * ⚠️ Affiché EN TOUTES LETTRES avec une teinte de fond : bleu en développement, vert
   * en recette. Un opérateur qui a les deux onglets ouverts n'a autrement aucun moyen
   * de savoir lequel est lequel — et les deux écrans sont identiques au pixel.
   */
  protected readonly environnement = environnementCourant();

  ngOnInit(): void {
    // Rediriger un utilisateur DÉJÀ connecté, sans redemander au serveur.
    //
    // ⚠️ Ce bloc appelait `getCurrentUser()`, donc un SECOND `GET /auth/me`. Le
    // constructeur d'`AuthService` (`providedIn: 'root'`) en lance déjà un à la
    // première injection — c'est-à-dire ici, ce composant étant le premier à
    // l'injecter sur cette route. Sur l'écran de connexion, la console affichait donc
    // deux 401 et deux erreurs, alors qu'un seul appel est nécessaire.
    //
    // On se contente d'écouter l'état que ce premier appel alimente. `currentUser$`
    // est un `BehaviorSubject` : il émet `null` immédiatement, puis l'utilisateur
    // quand la réponse arrive — d'où le `filter`, qui ignore le `null` initial.
    //
    // ⚠️ Zéro appel est impossible : le cookie de session est `HttpOnly`
    // (app/auth/routes.py), donc invisible à JavaScript. L'application ne peut pas
    // savoir si elle a une session sans le demander au serveur.
    this.authService.currentUser$
      .pipe(
        filter(user => user !== null),
        take(1),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe(() => {
        const returnUrl = this.route.snapshot.queryParams['returnUrl'] || '/dashboard';
        this.router.navigate([returnUrl]);
      });
  }

  /**
   * Initiate login flow
   */
  login(): void {
    const returnUrl = this.route.snapshot.queryParams['returnUrl'];
    this.authService.login(returnUrl);
  }
}

