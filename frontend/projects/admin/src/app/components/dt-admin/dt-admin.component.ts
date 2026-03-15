import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { BenevoleService, Benevole } from '../../services/benevole.service';
import { AuthService } from '../../services/auth.service';

/**
 * Bénévoles grouped by UL
 */
interface BenevolesByUL {
  ul: string;
  benevoles: Benevole[];
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
    MatSnackBarModule
  ],
  templateUrl: './dt-admin.component.html',
  styleUrl: './dt-admin.component.scss'
})
export class DtAdminComponent implements OnInit {
  private readonly benevoleService = inject(BenevoleService);
  private readonly authService = inject(AuthService);
  private readonly snackBar = inject(MatSnackBar);

  // State
  loading = signal(true);
  benevolesByUL = signal<BenevolesByUL[]>([]);
  currentUserDT = signal<string>('');

  ngOnInit(): void {
    // Get current user's DT
    this.authService.currentUser$.subscribe(user => {
      if (user) {
        this.currentUserDT.set(user.dt);
        this.loadBenevoles();
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
}

