import { Component, Input, Output, EventEmitter, inject, ChangeDetectorRef, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators, FormArray, FormControl } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { RepairService } from '../../services/repair.service';
import { Devis, Fournisseur } from '../../models/repair.model';
import { FournisseurSelectorComponent } from '../shared/fournisseur-selector.component';

@Component({
  selector: 'app-devis-form',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatDatepickerModule,
    MatNativeDateModule,
    MatButtonModule,
    MatIconModule,
    MatSnackBarModule,
    MatProgressSpinnerModule,
    FournisseurSelectorComponent,
  ],
  template: `
    <mat-card>
      <mat-card-header>
        <mat-card-title>Nouveau devis</mat-card-title>
      </mat-card-header>
      <mat-card-content>
        <form [formGroup]="form" (ngSubmit)="onSubmit()" (submit)="$event.stopPropagation()">
          <app-fournisseur-selector [dt]="dt" (fournisseurSelected)="onFournisseurSelected($event)"></app-fournisseur-selector>
          <div *ngIf="selectedFournisseur" class="selected-fournisseur">
            Fournisseur : <strong>{{ selectedFournisseur.nom }}</strong>
          </div>
          <div *ngIf="!selectedFournisseur && submitted" class="mat-error field-error">Un fournisseur est requis</div>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Date du devis</mat-label>
            <input matInput [matDatepicker]="picker" formControlName="date_devis">
            <mat-datepicker-toggle matIconSuffix [for]="picker"></mat-datepicker-toggle>
            <mat-datepicker #picker></mat-datepicker>
            <mat-error *ngIf="form.get('date_devis')?.hasError('required')">La date est requise</mat-error>
          </mat-form-field>

          <label class="section-label">Description des travaux (héritée du dossier)</label>
          <div class="description-items" formArrayName="descriptionItems">
            <div *ngFor="let item of descriptionItems.controls; let i = index" class="description-item-row">
              <mat-form-field appearance="outline" class="description-item-field">
                <mat-label>Élément {{ i + 1 }}</mat-label>
                <input matInput [formControlName]="i">
              </mat-form-field>
              <button mat-icon-button type="button" (click)="removeItem(i)" *ngIf="descriptionItems.length > 1" class="remove-btn">
                <mat-icon>close</mat-icon>
              </button>
            </div>
          </div>
          <button mat-stroked-button type="button" (click)="addItem()" class="add-item-btn">
            <mat-icon>add</mat-icon> Ajouter un élément
          </button>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Commentaire devis (optionnel)</mat-label>
            <textarea matInput formControlName="description_travaux" rows="2"></textarea>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Montant (€)</mat-label>
            <input matInput type="number" formControlName="montant" min="0" step="0.01">
            <mat-error *ngIf="form.get('montant')?.hasError('required')">Le montant est requis</mat-error>
            <mat-error *ngIf="form.get('montant')?.hasError('min')">Le montant doit être positif</mat-error>
          </mat-form-field>

          <div class="form-actions">
            <button mat-button type="button" (click)="cancelled.emit()">Annuler</button>
            <button mat-raised-button color="primary" type="submit" [disabled]="saving">
              {{ saving ? 'Enregistrement…' : 'Enregistrer le devis' }}
            </button>
          </div>
        </form>
      </mat-card-content>
    </mat-card>
  `,
  styles: [`
    .full-width { width: 100%; }
    .form-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
    .selected-fournisseur { margin-bottom: 16px; padding: 8px 12px; background: #e8f5e9; border-radius: 4px; }
    .field-error { font-size: 12px; color: #f44336; margin-bottom: 16px; }
    .section-label { font-weight: 500; display: block; margin-bottom: 8px; }
    .description-items { margin-bottom: 8px; }
    .description-item-row { display: flex; align-items: center; gap: 4px; }
    .description-item-field { flex: 1; }
    .remove-btn { flex-shrink: 0; }
    .add-item-btn { margin-bottom: 16px; }
  `],
})
export class DevisFormComponent implements OnInit {
  @Input() dt!: string;
  @Input() immat!: string;
  @Input() numero!: string;
  @Input() dossierDescription: string[] = [];
  @Output() devisCreated = new EventEmitter<Devis>();
  @Output() cancelled = new EventEmitter<void>();

  private readonly fb = inject(FormBuilder);
  private readonly repairService = inject(RepairService);
  private readonly snackBar = inject(MatSnackBar);
  private readonly cdr = inject(ChangeDetectorRef);

  selectedFournisseur: Fournisseur | null = null;
  saving = false;
  submitted = false;

  form = this.fb.group({
    date_devis: [new Date(), Validators.required],
    descriptionItems: this.fb.array([] as FormControl<string>[]),
    description_travaux: [''],
    montant: [null as number | null, [Validators.required, Validators.min(0.01)]],
  });

  get descriptionItems(): FormArray<FormControl<string>> {
    return this.form.get('descriptionItems') as FormArray<FormControl<string>>;
  }

  ngOnInit(): void {
    // Pre-populate description items from dossier
    const items = this.dossierDescription?.length ? this.dossierDescription : [''];
    items.forEach(item => {
      this.descriptionItems.push(this.fb.control(item) as FormControl<string>);
    });
  }

  addItem(): void {
    this.descriptionItems.push(this.fb.control('') as FormControl<string>);
  }

  removeItem(index: number): void {
    this.descriptionItems.removeAt(index);
  }

  onFournisseurSelected(f: Fournisseur): void {
    this.selectedFournisseur = f;
  }

  onSubmit(): void {
    this.submitted = true;
    if (this.form.invalid || !this.selectedFournisseur) return;

    this.saving = true;
    const v = this.form.value;
    const dateStr = v.date_devis instanceof Date
      ? v.date_devis.toISOString().split('T')[0]
      : String(v.date_devis);

    const descItems = this.descriptionItems.controls
      .map(c => c.value?.trim())
      .filter((val): val is string => !!val);

    this.repairService.createDevis(this.dt, this.immat, this.numero, {
      date_devis: dateStr,
      fournisseur_id: this.selectedFournisseur.id,
      description_items: descItems.length ? descItems : undefined,
      description_travaux: v.description_travaux?.trim() || undefined,
      montant: v.montant!,
    }).subscribe({
      next: (devis) => {
        this.saving = false;
        this.snackBar.open('Devis enregistré', 'Fermer', { duration: 3000 });
        this.cdr.detectChanges();
        this.devisCreated.emit(devis);
      },
      error: () => {
        this.saving = false;
        this.snackBar.open('Erreur lors de l\'enregistrement du devis', 'Fermer', { duration: 5000 });
        this.cdr.detectChanges();
      },
    });
  }
}

