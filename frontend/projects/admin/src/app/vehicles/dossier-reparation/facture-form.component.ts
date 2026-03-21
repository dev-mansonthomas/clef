import { Component, Input, Output, EventEmitter, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { RepairService } from '../../services/repair.service';
import { Devis, Fournisseur, FactureCreateResponse } from '../../models/repair.model';
import { FournisseurSelectorComponent } from '../shared/fournisseur-selector.component';

@Component({
  selector: 'app-facture-form',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
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
        <mat-card-title>Nouvelle facture</mat-card-title>
      </mat-card-header>
      <mat-card-content>
        <div *ngIf="warningNoDevis" class="warning-banner warning-yellow">
          <mat-icon>warning</mat-icon> Aucun devis approuvé pour ce dossier
        </div>
        <div *ngIf="warningEcart" class="warning-banner warning-orange">
          <mat-icon>warning</mat-icon> Écart de {{ ecartPourcentage }}% entre le devis et la facture
        </div>

        <form [formGroup]="form" (ngSubmit)="onSubmit()">
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Date de la facture</mat-label>
            <input matInput [matDatepicker]="picker" formControlName="date_facture">
            <mat-datepicker-toggle matIconSuffix [for]="picker"></mat-datepicker-toggle>
            <mat-datepicker #picker></mat-datepicker>
            <mat-error *ngIf="form.get('date_facture')?.hasError('required')">La date est requise</mat-error>
          </mat-form-field>

          <app-fournisseur-selector [dt]="dt" (fournisseurSelected)="onFournisseurSelected($event)"></app-fournisseur-selector>
          <div *ngIf="selectedFournisseur" class="selected-fournisseur">
            Fournisseur : <strong>{{ selectedFournisseur.nom }}</strong>
          </div>
          <div *ngIf="!selectedFournisseur && submitted" class="mat-error field-error">Un fournisseur est requis</div>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Classification</mat-label>
            <mat-select formControlName="classification">
              <mat-option *ngFor="let c of classifications" [value]="c.value">{{ c.label }}</mat-option>
            </mat-select>
            <mat-error *ngIf="form.get('classification')?.hasError('required')">La classification est requise</mat-error>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Description des travaux</mat-label>
            <textarea matInput formControlName="description_travaux" rows="3"></textarea>
            <mat-error *ngIf="form.get('description_travaux')?.hasError('required')">La description est requise</mat-error>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Montant total (€)</mat-label>
            <input matInput type="number" formControlName="montant_total" min="0" step="0.01">
            <mat-error *ngIf="form.get('montant_total')?.hasError('required')">Le montant total est requis</mat-error>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Montant CRF (€)</mat-label>
            <input matInput type="number" formControlName="montant_crf" min="0" step="0.01">
            <mat-error *ngIf="form.get('montant_crf')?.hasError('required')">Le montant CRF est requis</mat-error>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width" *ngIf="devisList.length">
            <mat-label>Devis associé (optionnel)</mat-label>
            <mat-select formControlName="devis_id">
              <mat-option [value]="null">Aucun</mat-option>
              <mat-option *ngFor="let d of devisList" [value]="d.id">
                #{{ d.id }} — {{ d.fournisseur_nom || d.fournisseur_id }} — {{ d.montant | number:'1.2-2' }} €
              </mat-option>
            </mat-select>
          </mat-form-field>

          <div class="form-actions">
            <button mat-button type="button" (click)="cancelled.emit()">Annuler</button>
            <button mat-raised-button color="primary" type="submit" [disabled]="saving">
              {{ saving ? 'Enregistrement…' : 'Enregistrer la facture' }}
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
    .warning-banner { display: flex; align-items: center; gap: 8px; padding: 12px 16px; border-radius: 4px; margin-bottom: 16px; font-weight: 500; }
    .warning-yellow { background: #fff9c4; color: #f9a825; }
    .warning-orange { background: #ffe0b2; color: #e65100; }
  `],
})
export class FactureFormComponent {
  @Input() dt!: string;
  @Input() immat!: string;
  @Input() numero!: string;
  @Input() devisList: Devis[] = [];
  @Output() factureCreated = new EventEmitter<FactureCreateResponse>();
  @Output() cancelled = new EventEmitter<void>();

  private readonly fb = inject(FormBuilder);
  private readonly repairService = inject(RepairService);
  private readonly snackBar = inject(MatSnackBar);

  selectedFournisseur: Fournisseur | null = null;
  saving = false;
  submitted = false;
  warningNoDevis = false;
  warningEcart = false;
  ecartPourcentage: number | null = null;

  classifications = [
    { value: 'entretien_courant', label: 'Entretien courant' },
    { value: 'reparation_carrosserie_mecanique', label: 'Réparation carrosserie / mécanique' },
    { value: 'reparation_sanitaire', label: 'Réparation sanitaire' },
    { value: 'reparation_marquage', label: 'Réparation marquage' },
    { value: 'controle_technique', label: 'Contrôle technique' },
    { value: 'frais_duplicata_carte_grise', label: 'Frais duplicata carte grise' },
    { value: 'autre', label: 'Autre' },
  ];

  form = this.fb.group({
    date_facture: [new Date(), Validators.required],
    classification: ['', Validators.required],
    description_travaux: ['', Validators.required],
    montant_total: [null as number | null, [Validators.required, Validators.min(0)]],
    montant_crf: [null as number | null, [Validators.required, Validators.min(0)]],
    devis_id: [null as number | null],
  });

  onFournisseurSelected(f: Fournisseur): void {
    this.selectedFournisseur = f;
  }

  onSubmit(): void {
    this.submitted = true;
    if (this.form.invalid || !this.selectedFournisseur) return;

    this.saving = true;
    const v = this.form.value;
    const dateStr = v.date_facture instanceof Date
      ? v.date_facture.toISOString().split('T')[0]
      : String(v.date_facture);

    this.repairService.createFacture(this.dt, this.immat, this.numero, {
      date_facture: dateStr,
      fournisseur_id: this.selectedFournisseur.id,
      classification: v.classification!,
      description_travaux: v.description_travaux!,
      montant_total: v.montant_total!,
      montant_crf: v.montant_crf!,
      devis_id: v.devis_id ?? undefined,
    }).subscribe({
      next: (result) => {
        this.saving = false;
        this.warningNoDevis = !!result.warning_no_devis;
        this.warningEcart = !!result.warning_ecart;
        this.ecartPourcentage = result.ecart_pourcentage ?? null;
        this.snackBar.open('Facture enregistrée', 'Fermer', { duration: 3000 });
        this.factureCreated.emit(result);
      },
      error: () => {
        this.saving = false;
        this.snackBar.open('Erreur lors de l\'enregistrement de la facture', 'Fermer', { duration: 5000 });
      },
    });
  }
}

