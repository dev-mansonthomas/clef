import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { StatsService, DashboardStats, VehicleAlert } from '../../services/stats.service';

/**
 * Dashboard component - main landing page after login
 */
@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatIconModule,
    MatProgressSpinnerModule
  ],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss'
})
export class DashboardComponent implements OnInit {
  private readonly statsService = inject(StatsService);
  private readonly router = inject(Router);

  // State
  loading = signal(true);
  stats = signal<DashboardStats | null>(null);
  error = signal<string | null>(null);

  ngOnInit(): void {
    this.loadStats();
  }

  /**
   * Load dashboard statistics
   */
  loadStats(): void {
    this.loading.set(true);
    this.error.set(null);

    this.statsService.getStats().subscribe({
      next: (stats) => {
        this.stats.set(stats);
        this.loading.set(false);
      },
      error: (err) => {
        console.error('Error loading stats:', err);
        this.error.set('Erreur lors du chargement des statistiques');
        this.loading.set(false);
      }
    });
  }

  /**
   * Get alert type label
   */
  getAlertLabel(alert: VehicleAlert): string {
    switch (alert.type) {
      case 'ct_expire':
        return `CT expiré il y a ${Math.abs(alert.jours)} jour${Math.abs(alert.jours) > 1 ? 's' : ''}`;
      case 'ct_bientot':
        return `CT dans ${alert.jours} jour${alert.jours > 1 ? 's' : ''}`;
      case 'pollution_expire':
        return `Pollution expiré il y a ${Math.abs(alert.jours)} jour${Math.abs(alert.jours) > 1 ? 's' : ''}`;
      case 'pollution_bientot':
        return `Pollution dans ${alert.jours} jour${alert.jours > 1 ? 's' : ''}`;
      default:
        return '';
    }
  }

  /**
   * Navigate to vehicle list with highlight
   */
  goToVehicle(immatriculation: string): void {
    this.router.navigate(['/vehicles'], {
      queryParams: { highlight: immatriculation }
    });
    this.router.navigate(['/vehicles']);
  }
}

