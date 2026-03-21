import { Component, Input, Output, EventEmitter, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { RepairService } from '../../services/repair.service';
import { DossierReparation } from '../../models/repair.model';

@Component({
  selector: 'app-dossier-create',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatSnackBarModule,
    MatProgressSpinnerModule,
  ],
  template: `
    <mat-card class="create-card">
      <mat-card-header>
        <mat-card-title>Nouveau dossier de réparation</mat-card-title>
      </mat-card-header>
      <mat-card-content>
        <form [formGroup]="form" (ngSubmit)="onSubmit()">
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Description des travaux</mat-label>
            <textarea matInput formControlName="description" rows="4" placeholder="Décrivez les réparations nécessaires…"></textarea>
            <mat-error *ngIf="form.get('description')?.hasError('required')">La description est requise</mat-error>
          </mat-form-field>

          <div class="form-actions">
            <button mat-button type="button" (click)="cancelled.emit()">Annuler</button>
            <button mat-raised-button color="primary" type="submit" [disabled]="form.invalid || saving">
              <mat-spinner *ngIf="saving" diameter="20" class="inline-spinner"></mat-spinner>
              <span *ngIf="!saving">Créer le dossier</span>
              <span *ngIf="saving">Création…</span>
            </button>
          </div>
        </form>
      </mat-card-content>
    </mat-card>
  `,
  styles: [`
    .create-card { margin-bottom: 16px; }
    .full-width { width: 100%; }
    .form-actions { display: flex; justify-content: flex-end; gap: 12px; margin-top: 8px; }
    .inline-spinner { display: inline-block; margin-right: 8px; }
  `],
})
export class DossierCreateComponent {
  @Input() dt!: string;
  @Input() immat!: string;
  @Output() created = new EventEmitter<DossierReparation>();
  @Output() cancelled = new EventEmitter<void>();

  private readonly fb = inject(FormBuilder);
  private readonly repairService = inject(RepairService);
  private readonly snackBar = inject(MatSnackBar);

  form = this.fb.group({
    description: ['', Validators.required],
  });

  saving = false;

  onSubmit(): void {
    if (this.form.invalid) return;
    this.saving = true;

    const description = this.form.value.description!;
    this.repairService.createDossier(this.dt, this.immat, { description }).subscribe({
      next: (dossier) => {
        this.snackBar.open('Dossier créé avec succès', 'Fermer', { duration: 3000 });
        this.saving = false;
        this.created.emit(dossier);
      },
      error: () => {
        this.snackBar.open('Erreur lors de la création du dossier', 'Fermer', { duration: 5000 });
        this.saving = false;
      },
    });
  }
}

