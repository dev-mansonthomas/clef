import { Component, OnInit, ViewChild, ElementRef, AfterViewInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatSliderModule } from '@angular/material/slider';
import SignaturePad from 'signature_pad';
import { CarnetBordService } from '../../services/carnet-bord.service';
import {
  PriseVehiculeRequest,
  NIVEAUX_CARBURANT_PRISE
} from '../../models/carnet-bord.model';

/**
 * Vehicle pickup (prise) form component
 * Captures: km, fuel level, condition, photos, signature
 */
@Component({
  selector: 'app-prise-form',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatIconModule,
    MatCardModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatSliderModule
  ],
  templateUrl: './prise-form.component.html',
  styleUrl: './prise-form.component.scss'
})
export class PriseFormComponent implements OnInit, AfterViewInit {
  @ViewChild('signatureCanvas', { static: false }) signatureCanvas!: ElementRef<HTMLCanvasElement>;

  priseForm!: FormGroup;
  signaturePad!: SignaturePad;
  loading = signal(false);
  photos = signal<File[]>([]);
  photoPreviewUrls = signal<string[]>([]);
  vehicleImmat = signal<string>('');
  readonly maxPhotos = 5;
  readonly niveauxCarburant = NIVEAUX_CARBURANT_PRISE;

  constructor(
    private fb: FormBuilder,
    private route: ActivatedRoute,
    private router: Router,
    private carnetBordService: CarnetBordService,
    private snackBar: MatSnackBar
  ) {}

  ngOnInit(): void {
    // Get vehicle from route params
    const immat = this.route.snapshot.paramMap.get('immat');
    if (immat) {
      this.vehicleImmat.set(immat);
    }

    this.initForm();
  }

  ngAfterViewInit(): void {
    this.initSignaturePad();
  }

  private initForm(): void {
    this.priseForm = this.fb.group({
      kmDepart: ['', [Validators.required, Validators.min(0)]],
      niveauCarburant: ['', Validators.required],
      etatGeneral: [5, [Validators.required, Validators.min(1), Validators.max(5)]],
      commentaires: ['']
    });
  }

  private initSignaturePad(): void {
    if (this.signatureCanvas) {
      const canvas = this.signatureCanvas.nativeElement;
      this.signaturePad = new SignaturePad(canvas, {
        backgroundColor: 'rgb(255, 255, 255)',
        penColor: 'rgb(0, 0, 0)'
      });

      // Resize canvas to fit container
      this.resizeCanvas();
    }
  }

  private resizeCanvas(): void {
    const canvas = this.signatureCanvas.nativeElement;
    const ratio = Math.max(window.devicePixelRatio || 1, 1);
    canvas.width = canvas.offsetWidth * ratio;
    canvas.height = canvas.offsetHeight * ratio;
    canvas.getContext('2d')!.scale(ratio, ratio);
    this.signaturePad.clear();
  }

  clearSignature(): void {
    this.signaturePad.clear();
  }

  onPhotoSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files) {
      const newFiles = Array.from(input.files);
      const currentPhotos = this.photos();

      if (currentPhotos.length + newFiles.length > this.maxPhotos) {
        this.snackBar.open(
          `Maximum ${this.maxPhotos} photos autorisées`,
          'Fermer',
          { duration: 3000 }
        );
        return;
      }

      // Add new photos
      this.photos.set([...currentPhotos, ...newFiles]);

      // Generate preview URLs
      newFiles.forEach(file => {
        const reader = new FileReader();
        reader.onload = (e) => {
          const currentUrls = this.photoPreviewUrls();
          this.photoPreviewUrls.set([...currentUrls, e.target!.result as string]);
        };
        reader.readAsDataURL(file);
      });

      // Reset input
      input.value = '';
    }
  }

  removePhoto(index: number): void {
    const currentPhotos = this.photos();
    const currentUrls = this.photoPreviewUrls();

    this.photos.set(currentPhotos.filter((_, i) => i !== index));
    this.photoPreviewUrls.set(currentUrls.filter((_, i) => i !== index));
  }

  onSubmit(): void {
    if (this.priseForm.invalid) {
      this.priseForm.markAllAsTouched();
      this.snackBar.open('Veuillez remplir tous les champs obligatoires', 'Fermer', { duration: 3000 });
      return;
    }

    if (this.signaturePad.isEmpty()) {
      this.snackBar.open('Veuillez signer le formulaire', 'Fermer', { duration: 3000 });
      return;
    }

    this.loading.set(true);

    // Prepare request data
    const formValue = this.priseForm.value;
    const request: PriseVehiculeRequest = {
      nomSynthetique: this.vehicleImmat(),
      kmDepart: formValue.kmDepart,
      niveauCarburant: formValue.niveauCarburant,
      etatGeneral: formValue.etatGeneral,
      commentaires: formValue.commentaires || '',
      signature: this.signaturePad.toDataURL(),
      datePrise: new Date().toISOString(),
      emailBenevole: 'user@example.com', // TODO: Get from auth service
      nomBenevole: 'User Name' // TODO: Get from auth service
    };

    // Submit form
    this.carnetBordService.submitPrise(request).subscribe({
      next: (response) => {
        this.loading.set(false);

        // Upload photos if any
        if (this.photos().length > 0) {
          this.uploadPhotos();
        } else {
          this.showSuccessAndNavigate();
        }
      },
      error: (error) => {
        this.loading.set(false);
        console.error('Error submitting prise form:', error);
        const message = error.error?.detail || 'Erreur lors de l\'enregistrement';
        this.snackBar.open(message, 'Fermer', { duration: 5000 });
      }
    });
  }

  private uploadPhotos(): void {
    this.carnetBordService.uploadPhotosPrise(this.vehicleImmat(), this.photos()).subscribe({
      next: (response) => {
        this.showSuccessAndNavigate();
      },
      error: (error) => {
        console.error('Error uploading photos:', error);
        this.snackBar.open(
          'Formulaire enregistré mais erreur lors de l\'upload des photos',
          'Fermer',
          { duration: 5000 }
        );
        this.showSuccessAndNavigate();
      }
    });
  }

  private showSuccessAndNavigate(): void {
    this.snackBar.open('Prise de véhicule enregistrée avec succès', 'Fermer', { duration: 3000 });
    // Navigate back to vehicle selector or home
    setTimeout(() => {
      this.router.navigate(['/']);
    }, 1500);
  }

  formatLabel(value: number): string {
    return `${value}/5`;
  }
}

