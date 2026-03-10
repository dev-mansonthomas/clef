import { Component, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { MatButtonModule } from '@angular/material/button';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { ReservationService } from '../../services/reservation.service';
import { Vehicle } from '../../models/vehicle.model';
import { Benevole } from '../../models/reservation.model';
import { map, startWith } from 'rxjs/operators';
import { Observable } from 'rxjs';

@Component({
  selector: 'app-reservation-form',
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatDatepickerModule,
    MatNativeDateModule,
    MatButtonModule,
    MatAutocompleteModule,
    MatProgressSpinnerModule,
    MatSnackBarModule
  ],
  templateUrl: './reservation-form.component.html',
  styleUrl: './reservation-form.component.scss'
})
export class ReservationFormComponent implements OnInit {
  reservationForm!: FormGroup;
  availableVehicles = signal<Vehicle[]>([]);
  benevoles = signal<Benevole[]>([]);
  filteredBenevoles!: Observable<Benevole[]>;
  loading = signal(false);
  loadingVehicles = signal(false);

  constructor(
    private fb: FormBuilder,
    private reservationService: ReservationService,
    private snackBar: MatSnackBar
  ) {}

  ngOnInit(): void {
    this.initForm();
    this.loadBenevoles();
    
    // Setup autocomplete filtering
    this.filteredBenevoles = this.reservationForm.get('chauffeur')!.valueChanges.pipe(
      startWith(''),
      map(value => this._filterBenevoles(value || ''))
    );
  }

  private initForm(): void {
    this.reservationForm = this.fb.group({
      startDate: [null, Validators.required],
      startTime: ['09:00', Validators.required],
      endDate: [null, Validators.required],
      endTime: ['17:00', Validators.required],
      vehicleIndicatif: ['', Validators.required],
      chauffeur: ['', Validators.required],
      mission: ['', Validators.required],
      description: ['']
    });

    // Watch date/time changes to reload available vehicles
    this.reservationForm.get('startDate')?.valueChanges.subscribe(() => this.loadAvailableVehicles());
    this.reservationForm.get('startTime')?.valueChanges.subscribe(() => this.loadAvailableVehicles());
    this.reservationForm.get('endDate')?.valueChanges.subscribe(() => this.loadAvailableVehicles());
    this.reservationForm.get('endTime')?.valueChanges.subscribe(() => this.loadAvailableVehicles());
  }

  private loadBenevoles(): void {
    this.reservationService.getBenevoles().subscribe({
      next: (response) => {
        this.benevoles.set(response.benevoles);
      },
      error: (error) => {
        console.error('Error loading benevoles:', error);
        this.snackBar.open('Erreur lors du chargement des bénévoles', 'Fermer', { duration: 3000 });
      }
    });
  }

  private loadAvailableVehicles(): void {
    const startDate = this.reservationForm.get('startDate')?.value;
    const startTime = this.reservationForm.get('startTime')?.value;
    const endDate = this.reservationForm.get('endDate')?.value;
    const endTime = this.reservationForm.get('endTime')?.value;

    if (!startDate || !startTime || !endDate || !endTime) {
      return;
    }

    const start = this.combineDateAndTime(startDate, startTime);
    const end = this.combineDateAndTime(endDate, endTime);

    if (end <= start) {
      this.snackBar.open('La date de fin doit être après la date de début', 'Fermer', { duration: 3000 });
      return;
    }

    this.loadingVehicles.set(true);
    this.reservationService.getAvailableVehicles(start.toISOString(), end.toISOString()).subscribe({
      next: (response) => {
        this.availableVehicles.set(response.vehicles);
        this.loadingVehicles.set(false);
      },
      error: (error) => {
        console.error('Error loading available vehicles:', error);
        this.snackBar.open('Erreur lors du chargement des véhicules disponibles', 'Fermer', { duration: 3000 });
        this.loadingVehicles.set(false);
      }
    });
  }

  private combineDateAndTime(date: Date, time: string): Date {
    const [hours, minutes] = time.split(':').map(Number);
    const combined = new Date(date);
    combined.setHours(hours, minutes, 0, 0);
    return combined;
  }

  private _filterBenevoles(value: string): Benevole[] {
    const filterValue = value.toLowerCase();
    return this.benevoles().filter(b => 
      `${b.prenom} ${b.nom}`.toLowerCase().includes(filterValue) ||
      b.email.toLowerCase().includes(filterValue)
    );
  }

  displayBenevole(benevole: Benevole | string): string {
    if (typeof benevole === 'string') {
      return benevole;
    }
    return benevole ? `${benevole.prenom} ${benevole.nom}` : '';
  }

  onSubmit(): void {
    if (this.reservationForm.invalid) {
      return;
    }

    const formValue = this.reservationForm.value;
    const start = this.combineDateAndTime(formValue.startDate, formValue.startTime);
    const end = this.combineDateAndTime(formValue.endDate, formValue.endTime);

    // Extract chauffeur name (handle both string and Benevole object)
    let chauffeurName: string;
    if (typeof formValue.chauffeur === 'string') {
      chauffeurName = formValue.chauffeur;
    } else {
      chauffeurName = `${formValue.chauffeur.prenom} ${formValue.chauffeur.nom}`;
    }

    const reservation = {
      indicatif: formValue.vehicleIndicatif,
      chauffeur: chauffeurName,
      mission: formValue.mission,
      start: start.toISOString(),
      end: end.toISOString(),
      description: formValue.description || undefined
    };

    this.loading.set(true);
    this.reservationService.createReservation(reservation).subscribe({
      next: (response) => {
        this.loading.set(false);
        this.snackBar.open('Réservation créée avec succès', 'Fermer', { duration: 3000 });
        this.reservationForm.reset({
          startTime: '09:00',
          endTime: '17:00'
        });
        this.availableVehicles.set([]);
        // TODO: Emit event to refresh calendar view
      },
      error: (error) => {
        this.loading.set(false);
        console.error('Error creating reservation:', error);
        const message = error.error?.detail || 'Erreur lors de la création de la réservation';
        this.snackBar.open(message, 'Fermer', { duration: 5000 });
      }
    });
  }
}

