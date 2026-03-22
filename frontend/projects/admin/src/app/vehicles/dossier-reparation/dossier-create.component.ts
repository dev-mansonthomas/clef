import { Component, Input, Output, EventEmitter, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators, FormArray, FormControl } from '@angular/forms';
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
        <form [formGroup]="form" (ngSubmit)="onSubmit()" (submit)="$event.stopPropagation()">
          <label class="section-label">Description des travaux</label>
          <div class="description-items" formArrayName="descriptionItems">
            <div *ngFor="let item of descriptionItems.controls; let i = index" class="description-item-row">
              <mat-form-field appearance="outline" class="description-item-field">
                <mat-label>Élément {{ i + 1 }}</mat-label>
                <input matInput [formControlName]="i" placeholder="Ex: Remplacement plaquettes de frein">
              </mat-form-field>
              <button mat-icon-button type="button" (click)="removeItem(i)" *ngIf="descriptionItems.length > 1" class="remove-btn">
                <mat-icon>close</mat-icon>
              </button>
            </div>
          </div>
          <button mat-stroked-button type="button" (click)="addItem()" class="add-item-btn">
            <mat-icon>add</mat-icon> Ajouter un élément
          </button>
          <div *ngIf="descriptionItems.length === 0 || allItemsEmpty()" class="mat-error item-error">
            Au moins un élément de description est requis
          </div>

          <mat-form-field appearance="outline" class="full-width commentaire-field">
            <mat-label>Commentaire (optionnel)</mat-label>
            <textarea matInput formControlName="commentaire" rows="2" placeholder="Commentaire libre…"></textarea>
          </mat-form-field>

          <div class="form-actions">
            <button mat-button type="button" (click)="cancelled.emit()">Annuler</button>
            <button mat-raised-button color="primary" type="submit" [disabled]="saving">
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
    .section-label { font-weight: 500; display: block; margin-bottom: 8px; }
    .description-items { margin-bottom: 8px; }
    .description-item-row { display: flex; align-items: center; gap: 4px; }
    .description-item-field { flex: 1; }
    .remove-btn { flex-shrink: 0; }
    .add-item-btn { margin-bottom: 16px; }
    .item-error { font-size: 12px; color: #f44336; margin-bottom: 16px; }
    .commentaire-field { margin-top: 8px; }
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
  private readonly cdr = inject(ChangeDetectorRef);

  form = this.fb.group({
    descriptionItems: this.fb.array([this.fb.control('', Validators.required)]),
    commentaire: [''],
  });

  saving = false;
  submitted = false;

  get descriptionItems(): FormArray<FormControl<string>> {
    return this.form.get('descriptionItems') as FormArray<FormControl<string>>;
  }

  addItem(): void {
    this.descriptionItems.push(this.fb.control('', Validators.required) as FormControl<string>);
  }

  removeItem(index: number): void {
    this.descriptionItems.removeAt(index);
  }

  allItemsEmpty(): boolean {
    return this.submitted && this.descriptionItems.controls.every(c => !c.value?.trim());
  }

  onSubmit(): void {
    this.submitted = true;
    const items = this.descriptionItems.controls
      .map(c => c.value?.trim())
      .filter((v): v is string => !!v);
    if (items.length === 0) return;
    this.saving = true;

    const commentaire = this.form.value.commentaire?.trim() || undefined;
    this.repairService.createDossier(this.dt, this.immat, { description: items, commentaire }).subscribe({
      next: (dossier) => {
        this.snackBar.open('Dossier créé avec succès', 'Fermer', { duration: 3000 });
        this.saving = false;
        this.cdr.detectChanges();
        this.created.emit(dossier);
      },
      error: () => {
        this.snackBar.open('Erreur lors de la création du dossier', 'Fermer', { duration: 5000 });
        this.saving = false;
        this.cdr.detectChanges();
      },
    });
  }
}

