import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatSelectModule } from '@angular/material/select';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatCardModule } from '@angular/material/card';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { VehicleService } from '../../services/vehicle.service';
import { ErrorService } from '../../services/error.service';
import { Vehicle, DisponibiliteStatus } from '../../models/vehicle.model';

@Component({
  selector: 'app-vehicle-edit',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatSelectModule,
    MatDatepickerModule,
    MatNativeDateModule,
    MatSnackBarModule,
    MatCardModule,
    MatProgressSpinnerModule
  ],
  templateUrl: './vehicle-edit.html',
  styleUrl: './vehicle-edit.scss',
})
export class VehicleEdit implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly vehicleService = inject(VehicleService);
  private readonly errorService = inject(ErrorService);
  private readonly snackBar = inject(MatSnackBar);
  private readonly cdr = inject(ChangeDetectorRef);

  vehicleForm!: FormGroup;
  loading = false;
  saving = false;
  nomSynthetique: string | null = null;
  vehicle: Vehicle | null = null;

  readonly disponibiliteOptions = [
    { value: 'Dispo', label: 'Disponible' },
    { value: 'Indispo', label: 'Indisponible' }
  ];

  readonly carteGriseOptions = ['Présente', 'Manquante', 'N/A', 'A Refabriquer'];

  readonly suiviModeOptions = [
    { value: 'prise', label: 'À la prise du véhicule' },
    { value: 'retour', label: 'Au retour du véhicule' },
    { value: 'prise_et_retour', label: 'À la prise et au retour du véhicule' }
  ];

  ngOnInit(): void {
    this.initForm();
    this.nomSynthetique = this.route.snapshot.paramMap.get('nomSynthetique');

    if (this.nomSynthetique) {
      this.loadVehicle();
    }
  }

  private initForm(): void {
    this.vehicleForm = this.fb.group({
      // Section: Identification
      dt_ul: ['', Validators.required],
      immat: ['', Validators.required],
      indicatif: ['', Validators.required],
      nom_synthetique: ['', Validators.required],

      // Section: Caractéristiques
      marque: ['', Validators.required],
      modele: ['', Validators.required],
      type: ['', Validators.required],
      date_mec: [''],
      nb_places: ['', Validators.required],
      carte_grise: ['', Validators.required],

      // Section: Disponibilité
      operationnel_mecanique: ['Dispo', Validators.required],
      raison_indispo: [''],

      // Section: Contrôles
      prochain_controle_technique: [''],
      prochain_controle_pollution: [''],

      // Section: Localisation & Instructions
      lieu_stationnement: [''],
      instructions_recuperation: [''],

      // Section: Administratif
      assurance_2026: [''],
      numero_serie_baus: [''],
      commentaires: [''],

      // Section: Metadata CLEF
      couleur_calendrier: ['#E30613'], // Default Red Cross color

      // Section: Configuration du suivi
      suivi_mode: ['prise'] // Default tracking mode
    });
  }

  private loadVehicle(): void {
    if (!this.nomSynthetique) return;

    this.loading = true;
    this.vehicleService.getVehicle(this.nomSynthetique).subscribe({
      next: (vehicle) => {
        this.vehicle = vehicle;
        this.populateForm(vehicle);
        this.loading = false;
        this.cdr.detectChanges();
      },
      error: (error) => {
        console.error('Error loading vehicle:', error);
        this.errorService.handleHttpError(error, 'Impossible de charger le véhicule. Veuillez réessayer.');
        this.loading = false;
        this.cdr.detectChanges();
        this.router.navigate(['/vehicles']);
      }
    });
  }

  private populateForm(vehicle: Vehicle): void {
    this.vehicleForm.patchValue({
      dt_ul: vehicle.dt_ul,
      immat: vehicle.immat,
      indicatif: vehicle.indicatif,
      nom_synthetique: vehicle.nom_synthetique,
      marque: vehicle.marque,
      modele: vehicle.modele,
      type: vehicle.type,
      date_mec: vehicle.date_mec,
      nb_places: vehicle.nb_places,
      carte_grise: vehicle.carte_grise,
      operationnel_mecanique: vehicle.operationnel_mecanique,
      raison_indispo: vehicle.raison_indispo,
      prochain_controle_technique: vehicle.prochain_controle_technique,
      prochain_controle_pollution: vehicle.prochain_controle_pollution,
      lieu_stationnement: vehicle.lieu_stationnement,
      instructions_recuperation: vehicle.instructions_recuperation,
      assurance_2026: vehicle.assurance_2026,
      numero_serie_baus: vehicle.numero_serie_baus,
      commentaires: vehicle.commentaires,
      suivi_mode: vehicle.suivi_mode || 'prise'
    });
  }

  onSubmit(): void {
    if (this.vehicleForm.invalid || !this.nomSynthetique) {
      return;
    }

    this.saving = true;
    const formValue = this.vehicleForm.value;

    // Only send metadata fields that can be updated
    const updateData = {
      couleur_calendrier: formValue.couleur_calendrier,
      commentaires: formValue.commentaires,
      suivi_mode: formValue.suivi_mode
    };

    this.vehicleService.updateVehicle(this.nomSynthetique, updateData).subscribe({
      next: () => {
        this.snackBar.open('Véhicule mis à jour avec succès', 'Fermer', {
          duration: 3000
        });
        this.saving = false;
        this.router.navigate(['/vehicles']);
      },
      error: (error) => {
        console.error('Error updating vehicle:', error);
        this.snackBar.open('Erreur lors de la mise à jour du véhicule', 'Fermer', {
          duration: 5000
        });
        this.saving = false;
      }
    });
  }

  onCancel(): void {
    this.router.navigate(['/vehicles']);
  }
}
