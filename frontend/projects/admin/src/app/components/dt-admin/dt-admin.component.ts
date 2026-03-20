import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatTableModule } from '@angular/material/table';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatChipsModule } from '@angular/material/chips';
import { BenevoleService, Benevole } from '../../services/benevole.service';
import { AuthService } from '../../services/auth.service';
import { UniteLocaleService } from '../../services/unite-locale.service';
import { UniteLocale } from '../../models/unite-locale.model';
import { ULDialogComponent } from './ul-dialog/ul-dialog.component';
import { environment } from '../../../environments/environment';

/**
 * Bénévoles grouped by UL
 */
interface BenevolesByUL {
  ul: string;
  benevoles: Benevole[];
}

/**
 * Calendar configuration
 */
interface CalendarConfig {
  configured: boolean;
  calendar_id?: string;
  calendar_url?: string;
}

/**
 * Google authorization status
 */
interface AuthorizationStatus {
  authorized: boolean;
  email?: string;
  authorized_at?: string;
  scopes?: string[];
}

/**
 * DT Administration component for managing volunteers and roles
 */
@Component({
  selector: 'app-dt-admin',
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatMenuModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatDialogModule,
    MatTableModule,
    MatTooltipModule,
    MatChipsModule
  ],
  templateUrl: './dt-admin.component.html',
  styleUrl: './dt-admin.component.scss'
})
export class DtAdminComponent implements OnInit {
  private readonly benevoleService = inject(BenevoleService);
  private readonly authService = inject(AuthService);
  private readonly uniteLocaleService = inject(UniteLocaleService);
  private readonly snackBar = inject(MatSnackBar);
  private readonly dialog = inject(MatDialog);
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  // State
  loading = signal(true);
  benevolesByUL = signal<BenevolesByUL[]>([]);
  currentUserDT = signal<string>('');

  // UL Management State
  unitesLocales = signal<UniteLocale[]>([]);
  ulLoading = signal(false);
  displayedColumns = ['id', 'nom', 'actions'];

  // Google Authorization State
  authorizationStatus = signal<AuthorizationStatus | null>(null);

  // Calendar Configuration State
  calendarConfig = signal<CalendarConfig | null>(null);
  creatingCalendar = signal(false);

  ngOnInit(): void {
    // Get current user's DT
    this.authService.currentUser$.subscribe(user => {
      if (user) {
        this.currentUserDT.set(user.dt);
        this.loadBenevoles();
        this.loadUnitesLocales();
        this.loadAuthorizationStatus();
        this.loadCalendarConfig();
      }
    });
  }

  /**
   * Load all bénévoles and group by UL
   */
  loadBenevoles(): void {
    this.loading.set(true);
    const dt = this.currentUserDT();
    
    this.benevoleService.getBenevoles(dt).subscribe({
      next: (response) => {
        // Group bénévoles by UL
        const grouped = this.groupByUL(response.benevoles);
        this.benevolesByUL.set(grouped);
        this.loading.set(false);
      },
      error: (error) => {
        console.error('Error loading bénévoles:', error);
        this.snackBar.open('Erreur lors du chargement des bénévoles', 'Fermer', {
          duration: 3000
        });
        this.loading.set(false);
      }
    });
  }

  /**
   * Group bénévoles by UL
   */
  private groupByUL(benevoles: Benevole[]): BenevolesByUL[] {
    const grouped = new Map<string, Benevole[]>();
    
    for (const benevole of benevoles) {
      const ul = benevole.ul || 'Sans UL';
      if (!grouped.has(ul)) {
        grouped.set(ul, []);
      }
      grouped.get(ul)!.push(benevole);
    }
    
    // Convert to array and sort by UL name
    return Array.from(grouped.entries())
      .map(([ul, benevoles]) => ({ ul, benevoles }))
      .sort((a, b) => a.ul.localeCompare(b.ul));
  }

  /**
   * Set bénévole as Responsable UL
   */
  setResponsableUL(benevole: Benevole): void {
    if (!benevole.ul) {
      this.snackBar.open('Le bénévole doit avoir une UL', 'Fermer', {
        duration: 3000
      });
      return;
    }

    const dt = this.currentUserDT();

    this.benevoleService.updateBenevoleRole(dt, benevole.email, {
      role: 'responsable_ul',
      ul: benevole.ul
    }).subscribe({
      next: () => {
        this.snackBar.open('Rôle mis à jour: Responsable UL', 'Fermer', {
          duration: 3000
        });
        this.loadBenevoles();
      },
      error: (error) => {
        console.error('Error updating role:', error);
        this.snackBar.open('Erreur lors de la mise à jour du rôle', 'Fermer', {
          duration: 3000
        });
      }
    });
  }

  /**
   * Remove role (set back to Bénévole)
   */
  removeRole(benevole: Benevole): void {
    const dt = this.currentUserDT();
    
    this.benevoleService.updateBenevoleRole(dt, benevole.email, {
      role: null,
      ul: null
    }).subscribe({
      next: () => {
        this.snackBar.open('Rôle retiré (Bénévole)', 'Fermer', {
          duration: 3000
        });
        this.loadBenevoles();
      },
      error: (error) => {
        console.error('Error updating role:', error);
        this.snackBar.open('Erreur lors de la mise à jour du rôle', 'Fermer', {
          duration: 3000
        });
      }
    });
  }

  /**
   * Check if a bénévole can be modified from this screen
   * DT Paris volunteers and responsable_dt cannot be modified here
   */
  canModifyBenevole(benevole: Benevole): boolean {
    return benevole.ul !== 'DT Paris' && benevole.role !== 'responsable_dt';
  }

  /**
   * Get display text for role
   */
  getRoleDisplay(role: string | null): string {
    if (!role || role === 'Bénévole') {
      return 'Bénévole';
    }
    if (role === 'Gestionnaire DT' || role === 'responsable_dt') {
      return 'Resp. DT';
    }
    if (role === 'Responsable UL' || role === 'responsable_ul') {
      return 'Resp. UL';
    }
    return role;
  }

  // ========== UL Management Methods ==========

  /**
   * Load all Unités Locales
   */
  loadUnitesLocales(): void {
    this.ulLoading.set(true);
    this.uniteLocaleService.getUnitesLocales().subscribe({
      next: (response) => {
        // Sort ULs by numeric ID
        const sortedULs = response.unites_locales.sort((a, b) =>
          parseInt(a.id, 10) - parseInt(b.id, 10)
        );
        this.unitesLocales.set(sortedULs);
        this.ulLoading.set(false);
      },
      error: (error) => {
        console.error('Error loading ULs:', error);
        this.snackBar.open('Erreur lors du chargement des ULs', 'Fermer', {
          duration: 3000
        });
        this.ulLoading.set(false);
      }
    });
  }

  /**
   * Open dialog to create a new UL
   */
  openCreateULDialog(): void {
    const dialogRef = this.dialog.open(ULDialogComponent, {
      width: '500px',
      data: { mode: 'create' }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.createUL(result);
      }
    });
  }

  /**
   * Open dialog to edit an existing UL
   */
  openEditULDialog(ul: UniteLocale): void {
    const dialogRef = this.dialog.open(ULDialogComponent, {
      width: '500px',
      data: { mode: 'edit', ul }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.updateUL(ul.id, result);
      }
    });
  }

  /**
   * Create a new UL
   */
  private createUL(data: { id: string; nom: string }): void {
    this.ulLoading.set(true);
    this.uniteLocaleService.createUniteLocale({
      id: data.id,
      nom: data.nom,
      dt: 'DT75'
    }).subscribe({
      next: () => {
        this.snackBar.open('UL créée avec succès', 'Fermer', {
          duration: 3000
        });
        this.loadUnitesLocales();
      },
      error: (error) => {
        console.error('Error creating UL:', error);
        const message = error.status === 409
          ? 'Cette UL existe déjà'
          : 'Erreur lors de la création de l\'UL';
        this.snackBar.open(message, 'Fermer', {
          duration: 3000
        });
        this.ulLoading.set(false);
      }
    });
  }

  /**
   * Update an existing UL
   */
  private updateUL(ulId: string, data: { nom: string }): void {
    this.ulLoading.set(true);
    this.uniteLocaleService.updateUniteLocale(ulId, { nom: data.nom }).subscribe({
      next: () => {
        this.snackBar.open('UL modifiée avec succès', 'Fermer', {
          duration: 3000
        });
        this.loadUnitesLocales();
      },
      error: (error) => {
        console.error('Error updating UL:', error);
        this.snackBar.open('Erreur lors de la modification de l\'UL', 'Fermer', {
          duration: 3000
        });
        this.ulLoading.set(false);
      }
    });
  }

  /**
   * Delete a UL with confirmation
   */
  deleteUL(ul: UniteLocale): void {
    if (confirm(`Êtes-vous sûr de vouloir supprimer l'UL "${ul.nom}" (${ul.id}) ?`)) {
      this.ulLoading.set(true);
      this.uniteLocaleService.deleteUniteLocale(ul.id).subscribe({
        next: () => {
          this.snackBar.open('UL supprimée avec succès', 'Fermer', {
            duration: 3000
          });
          this.loadUnitesLocales();
        },
        error: (error) => {
          console.error('Error deleting UL:', error);
          this.snackBar.open('Erreur lors de la suppression de l\'UL', 'Fermer', {
            duration: 3000
          });
          this.ulLoading.set(false);
        }
      });
    }
  }

  // ========== Google Authorization Methods ==========

  /**
   * Load Google authorization status
   */
  loadAuthorizationStatus(): void {
    this.http.get<AuthorizationStatus>(`${this.apiUrl}/auth/dt-authorization-status`)
      .subscribe({
        next: (status) => this.authorizationStatus.set(status),
        error: (err) => {
          console.error('Failed to load authorization status:', err);
          this.authorizationStatus.set({ authorized: false });
        }
      });
  }

  /**
   * Initiate Google OAuth authorization flow
   */
  authorizeGoogle(): void {
    this.http.get<{ authorization_url: string }>(`${this.apiUrl}/auth/authorize-dt`)
      .subscribe({
        next: (response) => {
          // Redirect to Google OAuth
          window.location.href = response.authorization_url;
        },
        error: (err) => {
          console.error('Failed to get authorization URL:', err);
          this.snackBar.open('Erreur lors de l\'autorisation', 'Fermer', { duration: 3000 });
        }
      });
  }

  /**
   * Revoke Google authorization
   */
  revokeAuthorization(): void {
    if (!confirm('Êtes-vous sûr de vouloir révoquer l\'autorisation ? Les fonctionnalités Calendar, Drive et Gmail ne fonctionneront plus.')) {
      return;
    }

    this.http.post(`${this.apiUrl}/auth/revoke-dt-authorization`, {})
      .subscribe({
        next: () => {
          this.authorizationStatus.set({ authorized: false });
          this.snackBar.open('Autorisation révoquée', 'OK', { duration: 3000 });
        },
        error: (err) => {
          console.error('Failed to revoke authorization:', err);
          this.snackBar.open('Erreur lors de la révocation', 'Fermer', { duration: 3000 });
        }
      });
  }

  // ========== Calendar Configuration Methods ==========

  /**
   * Load calendar configuration
   */
  loadCalendarConfig(): void {
    this.http.get<CalendarConfig>(`${this.apiUrl}/api/config/calendar`)
      .subscribe({
        next: (config) => this.calendarConfig.set(config),
        error: (err) => {
          console.error('Failed to load calendar config:', err);
          this.calendarConfig.set({ configured: false });
        }
      });
  }

  /**
   * Create a new Google Calendar
   */
  createCalendar(): void {
    this.creatingCalendar.set(true);

    this.http.post<{ calendar_id: string; calendar_url: string; message: string }>(`${this.apiUrl}/api/config/calendar`, {})
      .subscribe({
        next: (response) => {
          this.calendarConfig.set({
            configured: true,
            calendar_id: response.calendar_id,
            calendar_url: response.calendar_url,
          });
          this.snackBar.open(response.message, 'OK', { duration: 3000 });
          this.creatingCalendar.set(false);
        },
        error: (err) => {
          console.error('Failed to create calendar:', err);
          this.snackBar.open(err.error?.detail || 'Erreur lors de la création', 'Fermer', { duration: 5000 });
          this.creatingCalendar.set(false);
        }
      });
  }

  /**
   * Remove calendar configuration
   */
  removeCalendarConfig(): void {
    if (!confirm('Êtes-vous sûr de vouloir supprimer la configuration du calendrier ?')) {
      return;
    }

    this.http.delete(`${this.apiUrl}/api/config/calendar`)
      .subscribe({
        next: () => {
          this.calendarConfig.set({ configured: false });
          this.snackBar.open('Configuration supprimée', 'OK', { duration: 3000 });
        },
        error: (err) => {
          console.error('Failed to remove calendar config:', err);
          this.snackBar.open('Erreur lors de la suppression', 'Fermer', { duration: 3000 });
        }
      });
  }
}

