import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, ActivatedRoute } from '@angular/router';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { ReservationService } from '../../services/reservation.service';
import { VehicleService } from '../../services/vehicle.service';
import { AuthService } from '../../services/auth.service';
import { Vehicle } from '../../models/vehicle.model';
import { Benevole, ValkeyReservationCreate } from '../../models/reservation.model';
import { Observable, startWith, map } from 'rxjs';

/**
 * Reservation form component
 * Create or edit a vehicle reservation
 */
@Component({
  selector: 'app-reservation-form',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatDatepickerModule,
    MatNativeDateModule,
    MatAutocompleteModule
  ],
  templateUrl: './reservation-form.component.html',
  styleUrl: './reservation-form.component.scss'
})
export class ReservationFormComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly reservationService = inject(ReservationService);
  private readonly vehicleService = inject(VehicleService);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly snackBar = inject(MatSnackBar);

  reservationForm!: FormGroup;
  loading = signal(false);
  vehicles = signal<Vehicle[]>([]);
  benevoles = signal<Benevole[]>([]);
  filteredBenevoles!: Observable<Benevole[]>;
  isEditMode = signal(false);
  reservationId = signal<string | null>(null);

  ngOnInit(): void {
    this.initForm();
    this.loadVehicles();
    this.loadBenevoles();

    // Check if we're in edit mode
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.isEditMode.set(true);
      this.reservationId.set(id);
      this.loadReservation(id);
    }

    // Setup autocomplete filtering
    this.filteredBenevoles = this.reservationForm.get('chauffeur_nom')!.valueChanges.pipe(
      startWith(''),
      map(value => this._filterBenevoles(value || ''))
    );
  }

  private initForm(): void {
    this.reservationForm = this.fb.group({
      vehicule_immat: ['', Validators.required],
      chauffeur_nivol: ['', Validators.required],
      chauffeur_nom: ['', Validators.required],
      mission: ['', Validators.required],
      debut: ['', Validators.required],
      fin: ['', Validators.required],
      lieu_depart: [''],
      commentaire: ['']
    });
  }

  private loadVehicles(): void {
    this.vehicleService.getVehicles().subscribe({
      next: (response) => {
        this.vehicles.set(response.vehicles);
      },
      error: (error) => {
        console.error('Error loading vehicles:', error);
        this.snackBar.open('Erreur lors du chargement des véhicules', 'Fermer', {
          duration: 3000
        });
      }
    });
  }

  private loadBenevoles(): void {
    this.reservationService.getBenevoles().subscribe({
      next: (response) => {
        this.benevoles.set(response.benevoles);
      },
      error: (error) => {
        console.error('Error loading benevoles:', error);
        this.snackBar.open('Erreur lors du chargement des bénévoles', 'Fermer', {
          duration: 3000
        });
      }
    });
  }

  private loadReservation(id: string): void {
    this.loading.set(true);
    const dt = 'DT75';
    
    this.reservationService.getReservation(dt, id).subscribe({
      next: (reservation) => {
        this.reservationForm.patchValue({
          vehicule_immat: reservation.vehicule_immat,
          chauffeur_nivol: reservation.chauffeur_nivol,
          chauffeur_nom: reservation.chauffeur_nom,
          mission: reservation.mission,
          debut: new Date(reservation.debut),
          fin: new Date(reservation.fin),
          lieu_depart: reservation.lieu_depart,
          commentaire: reservation.commentaire
        });
        this.loading.set(false);
      },
      error: (error) => {
        console.error('Error loading reservation:', error);
        this.snackBar.open('Erreur lors du chargement de la réservation', 'Fermer', {
          duration: 3000
        });
        this.loading.set(false);
      }
    });
  }

  private _filterBenevoles(value: string): Benevole[] {
    const filterValue = value.toLowerCase();
    return this.benevoles().filter(benevole =>
      `${benevole.prenom} ${benevole.nom}`.toLowerCase().includes(filterValue) ||
      benevole.nivol.includes(filterValue)
    );
  }

  onBenevoleSelected(benevole: Benevole): void {
    this.reservationForm.patchValue({
      chauffeur_nivol: benevole.nivol,
      chauffeur_nom: `${benevole.prenom} ${benevole.nom}`
    });
  }

  displayBenevole(benevole: Benevole): string {
    return benevole ? `${benevole.prenom} ${benevole.nom}` : '';
  }

  onSubmit(): void {
    if (this.reservationForm.invalid) {
      this.snackBar.open('Veuillez remplir tous les champs obligatoires', 'Fermer', {
        duration: 3000
      });
      return;
    }

    this.loading.set(true);
    const dt = 'DT75';

    const formValue = this.reservationForm.value;
    const reservationData: ValkeyReservationCreate = {
      vehicule_immat: formValue.vehicule_immat,
      chauffeur_nivol: formValue.chauffeur_nivol,
      chauffeur_nom: formValue.chauffeur_nom,
      mission: formValue.mission,
      debut: new Date(formValue.debut).toISOString(),
      fin: new Date(formValue.fin).toISOString(),
      lieu_depart: formValue.lieu_depart || undefined,
      commentaire: formValue.commentaire || undefined
    };

    const operation = this.isEditMode() && this.reservationId()
      ? this.reservationService.updateReservation(dt, this.reservationId()!, reservationData)
      : this.reservationService.createReservation(dt, reservationData);

    operation.subscribe({
      next: () => {
        this.snackBar.open(
          this.isEditMode() ? 'Réservation modifiée' : 'Réservation créée',
          'Fermer',
          { duration: 3000 }
        );
        this.router.navigate(['/reservations']);
      },
      error: (error) => {
        console.error('Error saving reservation:', error);
        this.snackBar.open(
          error.error?.detail || 'Erreur lors de l\'enregistrement',
          'Fermer',
          { duration: 5000 }
        );
        this.loading.set(false);
      }
    });
  }

  cancel(): void {
    this.router.navigate(['/reservations']);
  }
}
