import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet, Router, RouterLink, RouterLinkActive } from '@angular/router';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatListModule } from '@angular/material/list';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatTooltipModule } from '@angular/material/tooltip';
import { AuthService } from '../../services/auth.service';
import { VehicleService } from '../../services/vehicle.service';
import { ConfigService } from '../../services/config.service';
import { forkJoin } from 'rxjs';

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
    MatButtonModule,
    MatTooltipModule
  ],
  templateUrl: './layout.component.html',
  styleUrl: './layout.component.scss'
})
export class LayoutComponent implements OnInit {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly vehicleService = inject(VehicleService);
  private readonly configService = inject(ConfigService);

  // Sidebar state
  sidenavOpened = signal(true);

  // Tutorial state
  showTutorial = signal(false);

  // Current user
  currentUser$ = this.authService.currentUser$;

  ngOnInit(): void {
    this.checkTutorialAutoShow();
  }

  /**
   * Auto-show tutorial if no vehicles or no drive folder configured
   */
  private checkTutorialAutoShow(): void {
    forkJoin({
      vehicles: this.vehicleService.getVehicles(),
      config: this.configService.getConfig()
    }).subscribe({
      next: ({ vehicles, config }) => {
        if (vehicles.count === 0 || !config.drive_folder_url) {
          this.showTutorial.set(true);
        }
      },
      error: () => {
        // On error, show tutorial as a safe default
        this.showTutorial.set(true);
      }
    });
  }

  /**
   * Toggle tutorial panel
   */
  toggleTutorial(): void {
    this.showTutorial.update(v => !v);
  }

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

