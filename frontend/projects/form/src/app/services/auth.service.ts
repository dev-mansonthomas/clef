import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
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
  private readonly apiUrl = environment.apiUrl || 'http://localhost:8000';

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
   */
  login(): void {
    this.http.get<LoginResponse>(`${this.apiUrl}/auth/login`).subscribe({
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
      catchError((error) => {
        console.error('Failed to get current user:', error);
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

