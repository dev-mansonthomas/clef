import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { ReservationService } from '../../services/reservation.service';
import { AuthService } from '../../services/auth.service';
import { ValkeyReservation } from '../../models/reservation.model';

/**
 * Reservation list component
 * Shows list of reservations with UL/DT toggle
 */
@Component({
  selector: 'app-reservation-list',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatButtonToggleModule
  ],
  templateUrl: './reservation-list.component.html',
  styleUrl: './reservation-list.component.scss'
})
export class ReservationListComponent implements OnInit {
  private readonly reservationService = inject(ReservationService);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly snackBar = inject(MatSnackBar);

  reservations = signal<ValkeyReservation[]>([]);
  loading = signal(false);
  view = signal<'ul' | 'dt'>('ul');
  currentUserEmail = signal<string>('');

  ngOnInit(): void {
    // Get current user email
    this.authService.currentUser$.subscribe(user => {
      if (user) {
        this.currentUserEmail.set(user.email);
      }
    });

    this.loadReservations();
  }

  /**
   * Load reservations based on current view
   */
  loadReservations(): void {
    this.loading.set(true);
    
    // For now, hardcode DT75 - in production this should come from user context
    const dt = 'DT75';
    
    this.reservationService.getReservations(dt, this.view()).subscribe({
      next: (response) => {
        this.reservations.set(response.reservations);
        this.loading.set(false);
      },
      error: (error) => {
        console.error('Error loading reservations:', error);
        this.snackBar.open('Erreur lors du chargement des réservations', 'Fermer', {
          duration: 3000
        });
        this.loading.set(false);
      }
    });
  }

  /**
   * Toggle between UL and DT view
   */
  onViewChange(newView: 'ul' | 'dt'): void {
    this.view.set(newView);
    this.loadReservations();
  }

  /**
   * Navigate to new reservation form
   */
  createReservation(): void {
    this.router.navigate(['/reservations/new']);
  }

  /**
   * Navigate to reservation detail
   */
  viewReservation(id: string): void {
    this.router.navigate(['/reservations', id]);
  }

  /**
   * Delete a reservation
   */
  deleteReservation(reservation: ValkeyReservation, event: Event): void {
    event.stopPropagation();
    
    if (!this.canDelete(reservation)) {
      this.snackBar.open('Vous ne pouvez supprimer que vos propres réservations', 'Fermer', {
        duration: 3000
      });
      return;
    }

    if (!confirm('Êtes-vous sûr de vouloir annuler cette réservation ?')) {
      return;
    }

    const dt = 'DT75';
    this.reservationService.deleteReservation(dt, reservation.id).subscribe({
      next: () => {
        this.snackBar.open('Réservation annulée', 'Fermer', {
          duration: 3000
        });
        this.loadReservations();
      },
      error: (error) => {
        console.error('Error deleting reservation:', error);
        this.snackBar.open('Erreur lors de l\'annulation', 'Fermer', {
          duration: 3000
        });
      }
    });
  }

  /**
   * Check if user can edit a reservation
   */
  canEdit(reservation: ValkeyReservation): boolean {
    return this.reservationService.canEdit(reservation, this.currentUserEmail());
  }

  /**
   * Check if user can delete a reservation
   */
  canDelete(reservation: ValkeyReservation): boolean {
    return this.reservationService.canDelete(reservation, this.currentUserEmail());
  }
}

