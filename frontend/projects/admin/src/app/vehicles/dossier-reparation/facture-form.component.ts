import { Component, Input, Output, EventEmitter, inject, ChangeDetectorRef, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormArray, FormControl, Validators } from '@angular/forms';
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
import { Devis, Facture, Fournisseur, FournisseurSnapshot, FactureCreateResponse } from '../../models/repair.model';
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
        <mat-card-title>{{ devisLabel ? 'Ajout d\'une facture au ' + devisLabel : (editFacture ? 'Modifier la facture' : 'Nouvelle facture') }}</mat-card-title>
      </mat-card-header>
      <mat-card-content>
        <div *ngIf="warningNoDevis" class="warning-banner warning-yellow">
          <mat-icon>warning</mat-icon> Aucun devis approuvé pour ce dossier
        </div>
        <div *ngIf="warningEcart" class="warning-banner warning-orange">
          <mat-icon>warning</mat-icon> Écart de {{ ecartPourcentage }}% entre le devis et la facture
        </div>

        <form [formGroup]="form" (ngSubmit)="onSubmit()" (submit)="$event.stopPropagation()">
          <app-fournisseur-selector [dt]="dt" [initialFournisseur]="initialFournisseurSnapshot" (fournisseurSelected)="onFournisseurSelected($event)"></app-fournisseur-selector>
          <div *ngIf="selectedFournisseur" class="selected-fournisseur">
            Fournisseur : <strong>{{ selectedFournisseur.nom }}</strong>
          </div>
          <div *ngIf="!selectedFournisseur && submitted" class="mat-error field-error">Un fournisseur est requis</div>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Date de la facture</mat-label>
            <input matInput [matDatepicker]="picker" formControlName="date_facture">
            <mat-datepicker-toggle matIconSuffix [for]="picker"></mat-datepicker-toggle>
            <mat-datepicker #picker></mat-datepicker>
            <mat-error *ngIf="form.get('date_facture')?.hasError('required')">La date est requise</mat-error>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Classification</mat-label>
            <mat-select formControlName="classification">
              <mat-option *ngFor="let c of classifications" [value]="c.value">{{ c.label }}</mat-option>
            </mat-select>
            <mat-error *ngIf="form.get('classification')?.hasError('required')">La classification est requise</mat-error>
          </mat-form-field>

          <div *ngIf="descriptionItems.length > 0" class="description-items-section">
            <label class="section-label">Travaux (hérités du devis)</label>
            <div *ngFor="let item of descriptionItems.controls; let i = index" class="description-item-row">
              <mat-form-field appearance="outline" class="description-item-field">
                <mat-label>Élément {{ i + 1 }}</mat-label>
                <input matInput [formControl]="item">
              </mat-form-field>
              <button mat-icon-button type="button" (click)="removeItem(i)">
                <mat-icon>close</mat-icon>
              </button>
            </div>
          </div>

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

          <div class="file-upload-section">
            <span class="section-label">Fichier facture (PDF/image)</span>
            <div class="file-input-row">
              <button mat-stroked-button type="button" (click)="factureFileInput.click()">
                <mat-icon>upload_file</mat-icon> {{ selectedFile ? 'Changer le fichier' : 'Joindre un fichier' }}
              </button>
              <span *ngIf="selectedFile" class="file-name">{{ selectedFile.name }}</span>
              <button mat-icon-button type="button" *ngIf="selectedFile" (click)="selectedFile = null">
                <mat-icon>close</mat-icon>
              </button>
            </div>
            <input #factureFileInput type="file" accept=".pdf,.jpg,.jpeg,.png" style="display:none" (change)="onFileInputChange($event)">
          </div>

          <mat-form-field appearance="outline" class="full-width" *ngIf="devisList.length">
            <mat-label>Devis associé (optionnel)</mat-label>
            <mat-select formControlName="devis_id">
              <mat-option [value]="null">Aucun</mat-option>
              <mat-option *ngFor="let d of devisList" [value]="d.id">
                #{{ d.id }} — {{ d.fournisseur.nom || d.id }} — {{ d.montant | number:'1.2-2' }} €
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
    .file-upload-section { margin-bottom: 16px; }
    .section-label { font-weight: 500; display: block; margin-bottom: 8px; }
    .file-input-row { display: flex; align-items: center; gap: 8px; }
    .file-name { font-size: 13px; color: rgba(0,0,0,0.7); }
    .description-items-section { margin-bottom: 16px; }
    .description-item-row { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
    .description-item-field { flex: 1; }
  `],
})
export class FactureFormComponent implements OnInit {
  @Input() dt!: string;
  @Input() immat!: string;
  @Input() numero!: string;
  @Input() devisList: Devis[] = [];
  @Input() preselectedDevisId: string | null = null;
  @Input() inheritedDescriptionItems: string[] = [];
  @Input() inheritedDescriptionTravaux: string = '';
  @Input() devisLabel: string | null = null;
  @Input() editFacture: Facture | null = null;
  @Output() factureCreated = new EventEmitter<FactureCreateResponse>();
  @Output() cancelled = new EventEmitter<void>();

  private readonly fb = inject(FormBuilder);
  private readonly repairService = inject(RepairService);
  private readonly snackBar = inject(MatSnackBar);
  private readonly cdr = inject(ChangeDetectorRef);

  selectedFournisseur: Fournisseur | null = null;
  initialFournisseurSnapshot: FournisseurSnapshot | null = null;
  selectedFile: File | null = null;
  saving = false;
  submitted = false;
  warningNoDevis = false;
  warningEcart = false;
  ecartPourcentage: number | null = null;

  classifications = [
    { value: 'entretien_courant', label: 'Entretien courant' },
    { value: 'reparation_carrosserie', label: 'Réparation carrosserie / mécanique' },
    { value: 'reparation_sanitaire', label: 'Réparation sanitaire' },
    { value: 'reparation_marquage', label: 'Réparation marquage' },
    { value: 'controle_technique', label: 'Contrôle technique' },
    { value: 'frais_duplicata_cg', label: 'Frais duplicata carte grise' },
    { value: 'autre', label: 'Autre' },
  ];

  form = this.fb.group({
    date_facture: [new Date(), Validators.required],
    classification: ['', Validators.required],
    description_travaux: ['', Validators.required],
    montant_total: [null as number | null, [Validators.required, Validators.min(0)]],
    montant_crf: [null as number | null, [Validators.required, Validators.min(0)]],
    devis_id: [null as string | null],
  });

  descriptionItems = this.fb.array<FormControl<string>>([]);

  ngOnInit(): void {
    if (this.editFacture) {
      // Edit mode — pre-fill form with existing facture data
      this.form.patchValue({
        date_facture: new Date(this.editFacture.date_facture),
        classification: this.editFacture.classification,
        description_travaux: this.editFacture.description_travaux || this.editFacture.description || '',
        montant_total: this.editFacture.montant_total,
        montant_crf: this.editFacture.montant_crf,
        devis_id: this.editFacture.devis_id || null,
      });
      this.initialFournisseurSnapshot = this.editFacture.fournisseur || null;
      if (this.editFacture.description_items?.length) {
        this.editFacture.description_items.forEach(item =>
          this.descriptionItems.push(this.fb.control(item) as FormControl<string>)
        );
      }
    } else if (this.preselectedDevisId) {
      const devis = this.devisList.find(d => String(d.id) === this.preselectedDevisId);
      if (devis) {
        this.form.patchValue({ devis_id: this.preselectedDevisId });
        this.initialFournisseurSnapshot = devis.fournisseur || null;

        // Inherit description items from devis
        const items = devis.description_items || this.inheritedDescriptionItems;
        if (items?.length) {
          items.forEach(item => this.descriptionItems.push(this.fb.control(item) as FormControl<string>));
        }

        // Inherit description_travaux from devis
        const travaux = devis.description_travaux || devis.description || this.inheritedDescriptionTravaux;
        if (travaux) {
          this.form.patchValue({ description_travaux: travaux });
        }
      }
    }
  }

  removeItem(index: number): void {
    this.descriptionItems.removeAt(index);
  }

  onFournisseurSelected(f: Fournisseur): void {
    this.selectedFournisseur = f;
  }

  onFileInputChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.selectedFile = input.files?.[0] || null;
    input.value = '';
  }

  onSubmit(): void {
    this.submitted = true;
    if (this.form.invalid || !this.selectedFournisseur) return;

    this.saving = true;
    const v = this.form.value;
    const dateStr = v.date_facture instanceof Date
      ? v.date_facture.toISOString().split('T')[0]
      : String(v.date_facture);

    const descItems = this.descriptionItems.controls
      .map(c => c.value?.trim())
      .filter((val): val is string => !!val);

    const factureData = {
      date_facture: dateStr,
      fournisseur_id: this.selectedFournisseur.id,
      fournisseur_nom: this.selectedFournisseur.nom,
      classification: v.classification!,
      description_travaux: v.description_travaux!,
      description_items: descItems.length ? descItems : undefined,
      montant_total: v.montant_total!,
      montant_crf: v.montant_crf!,
      devis_id: v.devis_id ?? undefined,
    };

    const request$ = this.editFacture
      ? this.repairService.updateFacture(this.dt, this.immat, this.numero, this.editFacture.id, factureData)
      : this.repairService.createFacture(this.dt, this.immat, this.numero, factureData);

    request$.subscribe({
      next: (result) => {
        this.warningNoDevis = !!result.warning_no_devis;
        this.warningEcart = !!result.warning_ecart;
        this.ecartPourcentage = result.ecart_pourcentage ?? null;

        if (this.selectedFile && result.id) {
          // Chain file upload after facture creation
          this.repairService.uploadFactureFile(this.dt, this.immat, this.numero, String(result.id), this.selectedFile).subscribe({
            next: () => {
              this.saving = false;
              this.snackBar.open('Facture et fichier enregistrés', 'Fermer', { duration: 3000 });
              this.cdr.detectChanges();
              this.factureCreated.emit(result);
            },
            error: () => {
              this.saving = false;
              this.snackBar.open('Facture enregistrée mais erreur lors de l\'upload du fichier', 'Fermer', { duration: 5000 });
              this.cdr.detectChanges();
              this.factureCreated.emit(result);
            },
          });
        } else {
          this.saving = false;
          this.snackBar.open('Facture enregistrée', 'Fermer', { duration: 3000 });
          this.cdr.detectChanges();
          this.factureCreated.emit(result);
        }
      },
      error: () => {
        this.saving = false;
        this.snackBar.open('Erreur lors de l\'enregistrement de la facture', 'Fermer', { duration: 5000 });
        this.cdr.detectChanges();
      },
    });
  }
}

