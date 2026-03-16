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
import { MatChipsModule } from '@angular/material/chips';
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
    MatProgressSpinnerModule,
    MatChipsModule
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
  isCreateMode = false;

  readonly disponibiliteOptions = [
    { value: 'Dispo', label: 'Disponible' },
    { value: 'Indispo', label: 'Indisponible' }
  ];

  readonly carteGriseOptions = ['Présente', 'Manquante', 'N/A', 'A Refabriquer'];

  readonly typeOptions = ['Log', 'PCM', 'Quad', 'Remorque', 'Utilitaire', 'VL', 'VPSP'];

  readonly suiviModeOptions = [
    { value: 'prise', label: 'Prise du véhicule' },
    { value: 'retour', label: 'Retour du véhicule' },
    { value: 'prise_et_retour', label: 'Prise et retour' }
  ];

  ngOnInit(): void {
    this.initForm();
    this.nomSynthetique = this.route.snapshot.paramMap.get('nomSynthetique');

    // Check if we're in create mode by examining the actual route URL
    // The route /vehicles/new/edit is a static route with no parameters
    const url = this.router.url;
    this.isCreateMode = url.includes('/vehicles/new/edit');

    if (this.nomSynthetique && !this.isCreateMode) {
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
      carte_grise: vehicle.carte_grise || 'Manquante',
      operationnel_mecanique: vehicle.operationnel_mecanique,
      raison_indispo: vehicle.raison_indispo,
      prochain_controle_technique: vehicle.prochain_controle_technique,
      prochain_controle_pollution: vehicle.prochain_controle_pollution,
      lieu_stationnement: vehicle.lieu_stationnement,
      instructions_recuperation: vehicle.instructions_recuperation,
      assurance_2026: vehicle.assurance_2026,
      numero_serie_baus: vehicle.numero_serie_baus,
      commentaires: vehicle.commentaires,
      suivi_mode: vehicle.suivi_mode  // Backend now provides type-based default
    });

    // Disable the 'type' field in edit mode (not create mode)
    // Using programmatic disable instead of [disabled] attribute to avoid Angular warning
    if (!this.isCreateMode) {
      this.vehicleForm.get('type')?.disable();
    }
  }

  onSubmit(): void {
    if (this.vehicleForm.invalid) {
      return;
    }

    this.saving = true;
    const formValue = this.vehicleForm.value;

    if (this.isCreateMode) {
      // Create new vehicle - send all fields
      const createData = {
        dt_ul: formValue.dt_ul,
        immat: formValue.immat,
        indicatif: formValue.indicatif,
        nom_synthetique: formValue.nom_synthetique,
        marque: formValue.marque,
        modele: formValue.modele,
        type: formValue.type,
        date_mec: formValue.date_mec || null,
        nb_places: formValue.nb_places,
        carte_grise: formValue.carte_grise,
        operationnel_mecanique: formValue.operationnel_mecanique,
        raison_indispo: formValue.raison_indispo || '',
        prochain_controle_technique: formValue.prochain_controle_technique || null,
        prochain_controle_pollution: formValue.prochain_controle_pollution || null,
        lieu_stationnement: formValue.lieu_stationnement || '',
        instructions_recuperation: formValue.instructions_recuperation || '',
        assurance_2026: formValue.assurance_2026 || '',
        numero_serie_baus: formValue.numero_serie_baus || '',
        commentaires: formValue.commentaires || '',
        suivi_mode: formValue.suivi_mode
      };

      this.vehicleService.createVehicle(createData).subscribe({
        next: (vehicle) => {
          this.snackBar.open('Véhicule créé avec succès', 'Fermer', {
            duration: 3000
          });
          this.saving = false;
          // Navigate to vehicle list with highlight on the new vehicle
          this.router.navigate(['/vehicles'], {
            queryParams: { highlight: vehicle.immat }
          });
        },
        error: (error) => {
          console.error('Error creating vehicle:', error);
          this.errorService.handleHttpError(error, 'Erreur lors de la création du véhicule');
          this.saving = false;
        }
      });
    } else {
      // Update existing vehicle - only send metadata fields that can be updated
      if (!this.nomSynthetique) {
        return;
      }

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
  }

  onCancel(): void {
    this.router.navigate(['/vehicles']);
  }

  /**
   * Check if there are any alerts to display
   */
  hasAlerts(): boolean {
    if (!this.vehicle) return false;

    return this.vehicle.status_disponibilite.value === 'Indispo' ||
           !this.vehicle.carte_grise ||
           this.vehicle.carte_grise === 'Manquante' ||
           this.isCtExpired() ||
           this.isPollutionExpired();
  }

  /**
   * Check if CT (contrôle technique) is expired
   */
  isCtExpired(): boolean {
    const v = this.vehicle;
    // Pas de date = pas d'alerte (rien à vérifier)
    if (!v?.prochain_controle_technique) return false;
    // Only show alert if there's a date AND it's expired (red)
    return v.status_ct?.color === 'red';
  }

  /**
   * Check if pollution control is expired
   */
  isPollutionExpired(): boolean {
    const v = this.vehicle;
    // Pas de date = pas d'alerte (rien à vérifier)
    if (!v?.prochain_controle_pollution) return false;
    // Only show alert if there's a date AND it's expired (red)
    return v.status_pollution?.color === 'red';
  }

  /**
   * Check if carte grise is missing
   */
  isCarteGriseMissing(): boolean {
    if (!this.vehicle) return false;
    return this.vehicle.carte_grise === 'Manquante';
  }

  /**
   * Check if vehicle is unavailable
   */
  isVehicleUnavailable(): boolean {
    if (!this.vehicle) return false;
    return this.vehicle.status_disponibilite?.value === 'Indispo';
  }

  /**
   * Get CSS class for Disponibilité field based on value
   */
  getDisponibiliteClass(): string {
    const value = this.vehicleForm?.get('operationnel_mecanique')?.value;
    if (value === 'Dispo') return 'field-success';
    if (value === 'Indispo') return 'field-alert';
    return '';
  }

  /**
   * Get CSS class for Carte Grise field based on value
   */
  getCarteGriseClass(): string {
    const value = this.vehicleForm?.get('carte_grise')?.value;
    if (value === 'Manquante') return 'field-alert';
    if (value === 'Présente') return 'field-success';
    if (value === 'A Refabriquer') return 'field-warning';
    if (value === 'N/A') return 'field-neutral';
    return '';
  }

  /**
   * Get CSS class for CT field based on status
   */
  getCtClass(): string {
    if (!this.vehicle?.status_ct) return '';
    const color = this.vehicle.status_ct.color;
    if (color === 'red') return 'field-alert';
    if (color === 'orange') return 'field-warning';
    if (color === 'green') return 'field-success';
    return '';
  }
}
