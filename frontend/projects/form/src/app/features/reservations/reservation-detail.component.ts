import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { ReservationService } from '../../services/reservation.service';
import { AuthService } from '../../services/auth.service';
import { ValkeyReservation } from '../../models/reservation.model';

/**
 * Reservation detail component
 * Shows details of a single reservation
 */
@Component({
  selector: 'app-reservation-detail',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSnackBarModule
  ],
  templateUrl: './reservation-detail.component.html',
  styleUrl: './reservation-detail.component.scss'
})
export class ReservationDetailComponent implements OnInit {
  private readonly reservationService = inject(ReservationService);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly snackBar = inject(MatSnackBar);

  reservation = signal<ValkeyReservation | null>(null);
  loading = signal(false);
  currentUserEmail = signal<string>('');

  ngOnInit(): void {
    // Get current user email
    this.authService.currentUser$.subscribe(user => {
      if (user) {
        this.currentUserEmail.set(user.email);
      }
    });

    // Load reservation
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.loadReservation(id);
    }
  }

  private loadReservation(id: string): void {
    this.loading.set(true);
    const dt = 'DT75';
    
    this.reservationService.getReservation(dt, id).subscribe({
      next: (reservation) => {
        this.reservation.set(reservation);
        this.loading.set(false);
      },
      error: (error) => {
        console.error('Error loading reservation:', error);
        this.snackBar.open('Erreur lors du chargement de la réservation', 'Fermer', {
          duration: 3000
        });
        this.loading.set(false);
        this.router.navigate(['/reservations']);
      }
    });
  }

  canEdit(): boolean {
    const res = this.reservation();
    return res ? this.reservationService.canEdit(res, this.currentUserEmail()) : false;
  }

  canDelete(): boolean {
    const res = this.reservation();
    return res ? this.reservationService.canDelete(res, this.currentUserEmail()) : false;
  }

  deleteReservation(): void {
    const res = this.reservation();
    if (!res || !this.canDelete()) {
      return;
    }

    if (!confirm('Êtes-vous sûr de vouloir annuler cette réservation ?')) {
      return;
    }

    const dt = 'DT75';
    this.reservationService.deleteReservation(dt, res.id).subscribe({
      next: () => {
        this.snackBar.open('Réservation annulée', 'Fermer', {
          duration: 3000
        });
        this.router.navigate(['/reservations']);
      },
      error: (error) => {
        console.error('Error deleting reservation:', error);
        this.snackBar.open('Erreur lors de l\'annulation', 'Fermer', {
          duration: 3000
        });
      }
    });
  }

  goBack(): void {
    this.router.navigate(['/reservations']);
  }
}

