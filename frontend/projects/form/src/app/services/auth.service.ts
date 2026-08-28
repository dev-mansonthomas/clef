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
   * @param returnUrl Route Angular où revenir après connexion (ex. '/vehicle/abc')
   */
  login(returnUrl?: string): void {
    // ⚠️ Le chemin doit passer par `prepareExternalUrl`, qui préfixe le BASE HREF.
    //
    // Cette application est servie sous `/form/`, et `returnUrl` est une route
    // ANGULAR, donc relative à ce préfixe. Cette méthode envoyait
    // `window.location.origin` tout court : après connexion, le bénévole atterrissait
    // sur la page d'accueil du domaine, pas dans son application — et un `returnUrl`
    // était purement ignoré, alors que le composant de connexion en reçoit un.
    //
    // Même défaut que dans l'application admin, où il donnait un 404 de nginx sur
    // `/dashboard` (le domaine sert `/admin/dashboard`).
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
        // Un 401 ici est la réponse ATTENDUE sans session : c'est ainsi que
        // l'application apprend qu'elle n'est pas connectée. Le journaliser en
        // `error` noyait les pannes réelles sous du rouge attendu.
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
}

