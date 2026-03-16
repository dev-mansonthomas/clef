import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet, Router, RouterLink, RouterLinkActive } from '@angular/router';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatListModule } from '@angular/material/list';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { AuthService } from '../../services/auth.service';

/**
 * Main layout component with Material Design sidebar
 */
@Component({
  selector: 'app-layout',
  standalone: true,
  imports: [
    CommonModule,
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    MatToolbarModule,
    MatSidenavModule,
    MatListModule,
    MatIconModule,
    MatButtonModule
  ],
  templateUrl: './layout.component.html',
  styleUrl: './layout.component.scss'
})
export class LayoutComponent {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  
  // Sidebar state
  sidenavOpened = signal(true);
  
  // Current user
  currentUser$ = this.authService.currentUser$;

  /**
   * Toggle sidebar
   */
  toggleSidenav(): void {
    this.sidenavOpened.update(value => !value);
  }

  /**
   * Logout user
   */
  logout(): void {
    this.authService.logout().subscribe();
  }

  /**
   * Check if user is DT Manager
   */
  isDTManager(user: any): boolean {
    return this.authService.isDTManager(user);
  }
}

