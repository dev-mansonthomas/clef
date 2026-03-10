import { Component, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';
import { ActivatedRoute, Router } from '@angular/router';
import { CarnetBordService } from '../../services/carnet-bord.service';
import { 
  NIVEAUX_CARBURANT, 
  ETATS_GENERAL,
  RetourVehiculeRequest,
  PriseVehiculeData
} from '../../models/carnet-bord.model';

@Component({
  selector: 'app-retour-form',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatCheckboxModule,
    MatButtonModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatIconModule,
    MatCardModule
  ],
  templateUrl: './retour-form.component.html',
  styleUrl: './retour-form.component.scss'
})
export class RetourFormComponent implements OnInit {
  retourForm!: FormGroup;
  loading = signal(false);
  loadingPriseData = signal(false);
  selectedPhotos = signal<File[]>([]);
  priseData = signal<PriseVehiculeData | null>(null);
  
  readonly niveauxCarburant = NIVEAUX_CARBURANT;
  readonly etatsGeneral = ETATS_GENERAL;
  
  // Computed: km parcourus
  kmParcourus = computed(() => {
    const prise = this.priseData();
    const kmArrivee = this.retourForm?.get('kmArrivee')?.value;

    if (prise && kmArrivee && kmArrivee > prise.kilometrage) {
      return kmArrivee - prise.kilometrage;
    }
    return null;
  });
  
  // Computed: show problem fields
  showProblemFields = computed(() => {
    return this.retourForm?.get('problemeASignaler')?.value === true;
  });

  constructor(
    private fb: FormBuilder,
    private route: ActivatedRoute,
    private router: Router,
    private carnetBordService: CarnetBordService,
    private snackBar: MatSnackBar
  ) {}

  ngOnInit(): void {
    this.initForm();
    
    // Get vehicle from route params or QR scan
    const nomSynthetique = this.route.snapshot.paramMap.get('nomSynthetique');
    if (nomSynthetique) {
      this.loadPriseData(nomSynthetique);
    }
  }

  private initForm(): void {
    this.retourForm = this.fb.group({
      nomSynthetique: ['', Validators.required],
      kmArrivee: ['', [Validators.required, Validators.min(0)]],
      niveauCarburant: ['', Validators.required],
      etatGeneral: ['Bon', Validators.required],
      problemeASignaler: [false],
      descriptionProbleme: ['']
    });
    
    // Add conditional validation for problem description
    this.retourForm.get('problemeASignaler')?.valueChanges.subscribe(checked => {
      const descControl = this.retourForm.get('descriptionProbleme');
      if (checked) {
        descControl?.setValidators([Validators.required, Validators.minLength(10)]);
      } else {
        descControl?.clearValidators();
      }
      descControl?.updateValueAndValidity();
    });
  }

  private loadPriseData(nomSynthetique: string): void {
    this.loadingPriseData.set(true);
    this.carnetBordService.getRecentPrise(nomSynthetique).subscribe({
      next: (data) => {
        this.loadingPriseData.set(false);
        this.priseData.set(data);
        this.retourForm.patchValue({ nomSynthetique });
      },
      error: (error) => {
        this.loadingPriseData.set(false);
        console.error('Error loading prise data:', error);
        this.snackBar.open(
          'Impossible de charger les données de prise',
          'Fermer',
          { duration: 5000 }
        );
      }
    });
  }

  onPhotoSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files) {
      const newPhotos = Array.from(input.files);
      this.selectedPhotos.update(photos => [...photos, ...newPhotos]);
    }
  }

  removePhoto(index: number): void {
    this.selectedPhotos.update(photos => photos.filter((_, i) => i !== index));
  }

  onSubmit(): void {
    if (this.retourForm.invalid) {
      return;
    }

    const formValue = this.retourForm.value;
    const prise = this.priseData();

    // TODO: Get actual user data from auth service
    const request: RetourVehiculeRequest = {
      vehicule_id: formValue.nomSynthetique,
      benevole_email: 'user@croix-rouge.fr', // TODO: from auth
      benevole_nom: 'Nom', // TODO: from auth
      benevole_prenom: 'Prénom', // TODO: from auth
      kilometrage: formValue.kmArrivee,
      niveau_carburant: formValue.niveauCarburant,
      etat_general: formValue.etatGeneral,
      problemes_signales: formValue.problemeASignaler ? formValue.descriptionProbleme : '',
      observations: '',
      timestamp: new Date().toISOString()
    };

    this.loading.set(true);
    this.carnetBordService.submitRetour(request).subscribe({
      next: (response) => {
        this.loading.set(false);

        // Calculate km parcourus for display
        let message = 'Retour enregistré avec succès';
        if (prise && formValue.kmArrivee > prise.kilometrage) {
          const kmParcourus = formValue.kmArrivee - prise.kilometrage;
          message += ` (${kmParcourus} km parcourus)`;
        }

        this.snackBar.open(message, 'Fermer', { duration: 5000 });

        // Navigate back or to home
        this.router.navigate(['/']);
      },
      error: (error) => {
        this.loading.set(false);
        console.error('Error submitting retour:', error);
        const message = error.error?.detail || 'Erreur lors de l\'enregistrement du retour';
        this.snackBar.open(message, 'Fermer', { duration: 5000 });
      }
    });
  }
}

