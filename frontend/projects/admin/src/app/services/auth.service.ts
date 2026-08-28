import { Injectable, inject, signal } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Router } from '@angular/router';
import { Location } from '@angular/common';
import { Observable, BehaviorSubject, tap, catchError, of } from 'rxjs';
import { User } from '../models/user.model';
import { environment } from '../../environments/environment';

interface LoginResponse {
  authorization_url: string;
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly location = inject(Location);
  private readonly apiUrl = environment.apiUrl;

  // Current user state
  private currentUserSubject = new BehaviorSubject<User | null>(null);
  public currentUser$ = this.currentUserSubject.asObservable();

  // Authentication state signal
  public isAuthenticated = signal(false);

  constructor() {
    // Check authentication status on service initialization
    this.checkAuthStatus();
  }

  /**
   * Initiate login flow - redirects to Google OAuth
   * @param returnUrl Optional path to redirect to after login (e.g. '/approbation/token-123')
   */
  login(returnUrl?: string): void {
    // ⚠️ Le chemin doit passer par `prepareExternalUrl`, qui préfixe le BASE HREF.
    //
    // Les deux applications sont servies sous un sous-chemin (`/admin/`), et
    // `returnUrl` est une route ANGULAR — « /dashboard » — donc relative à ce
    // préfixe. Concaténée à `window.location.origin`, elle donnait
    // « https://dev.clef.paquerette.com/dashboard » : un 404 de nginx après une
    // authentification pourtant réussie, constaté au premier déploiement du domaine.
    // `prepareExternalUrl` rend « /admin/dashboard ».
    //
    // Même famille que les redirections `/vehicle/…` et `/approbation/…` du gabarit
    // nginx : une URL fabriquée d'un côté, servie sous un préfixe de l'autre.
    const chemin = this.location.prepareExternalUrl(returnUrl ?? '/');
    const redirectTo = window.location.origin + chemin;

    this.http.get<LoginResponse>(`${this.apiUrl}/auth/login`, {
      params: { redirect_to: redirectTo }
    }).subscribe({
      next: (response) => {
        // Redirect to Google OAuth authorization URL
        window.location.href = response.authorization_url;
      },
      error: (error) => {
        console.error('Login failed:', error);
      }
    });
  }

  /**
   * Logout user
   */
  logout(): Observable<any> {
    return this.http.post(`${this.apiUrl}/auth/logout`, {}).pipe(
      tap(() => {
        this.currentUserSubject.next(null);
        this.isAuthenticated.set(false);
        this.router.navigate(['/login']);
      })
    );
  }

  /**
   * Get current authenticated user
   */
  getCurrentUser(): Observable<User | null> {
    return this.http.get<User>(`${this.apiUrl}/auth/me`).pipe(
      tap((user) => {
        this.currentUserSubject.next(user);
        this.isAuthenticated.set(true);
      }),
      catchError((error: unknown) => {
        // Un 401 ici est la réponse ATTENDUE quand il n'y a pas de session : c'est
        // ainsi que l'application apprend qu'elle n'est pas connectée. Le journaliser
        // en `error` remplissait la console de rouge sur l'écran de connexion, où
        // c'est le cas normal — et noyait les pannes réelles.
        //
        // ⚠️ La ligne « GET /auth/me 401 » du navigateur, elle, est émise par le
        // navigateur lui-même : aucun code ne la supprime. Seul le fait de ne pas
        // faire la requête l'enlève, ce qui est impossible ici (cookie `HttpOnly`).
        if (!(error instanceof HttpErrorResponse) || error.status !== 401) {
          console.error('Failed to get current user:', error);
        }
        this.currentUserSubject.next(null);
        this.isAuthenticated.set(false);
        return of(null);
      })
    );
  }

  /**
   * Check if user is authenticated
   */
  private checkAuthStatus(): void {
    this.getCurrentUser().subscribe();
  }

  /**
   * Get current user value (synchronous)
   */
  get currentUserValue(): User | null {
    return this.currentUserSubject.value;
  }

  /**
   * Check if user is DT Manager
   */
  isDTManager(user: User | null): boolean {
    return user?.role === 'Gestionnaire DT';
  }

  /**
   * Check if user is Super Admin
   */
  isSuperAdmin(user: User | null): boolean {
    return user?.is_super_admin === true;
  }

  /**
   * Check if user is UL Responsable
   */
  isUlResponsable(user: User | null): boolean {
    return user?.role === 'Responsable UL';
  }
}

