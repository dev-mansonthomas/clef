import { Component, Input, Output, EventEmitter, OnInit, OnChanges, SimpleChanges, inject, ChangeDetectorRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule, FormControl } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatDividerModule } from '@angular/material/divider';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatDialogModule } from '@angular/material/dialog';
import { MatAutocompleteModule, MatAutocompleteTrigger } from '@angular/material/autocomplete';
import { Observable, startWith, map } from 'rxjs';
import { RepairService } from '../../services/repair.service';
import { ValideurService } from '../../services/valideur.service';
import { DossierReparation, Devis, FactureCreateResponse, AuditEntry, Valideur } from '../../models/repair.model';
import { DevisFormComponent } from './devis-form.component';
import { FactureFormComponent } from './facture-form.component';

@Component({
  selector: 'app-dossier-detail',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatChipsModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatDividerModule,
    MatFormFieldModule,
    MatInputModule,
    MatDialogModule,
    MatAutocompleteModule,
    DevisFormComponent,
    FactureFormComponent,
  ],
  template: `
    <div class="dossier-detail" *ngIf="!loading && dossier">
      <div class="detail-header">
        <button mat-button type="button" (click)="back.emit()"><mat-icon>arrow_back</mat-icon> Retour à la liste</button>
      </div>

      <mat-card>
        <mat-card-header class="dossier-header-row">
          <mat-card-title class="dossier-header-inline">
            <span>{{ dossier.numero }}</span>
            <span class="header-separator">·</span>
            <span class="header-date">Créé le {{ dossier.cree_le | date:'dd/MM/yyyy HH:mm' }}</span>
            <span class="header-separator">·</span>
            <span class="statut-badge" [ngClass]="'statut-' + dossier.statut">{{ statutLabel(dossier.statut) }}</span>
          </mat-card-title>
        </mat-card-header>
        <mat-card-content>

          <h4>Description</h4>
          <ul class="description-list" *ngIf="dossier.description?.length">
            <li *ngFor="let item of dossier.description">{{ item }}</li>
          </ul>
          <p class="empty-section" *ngIf="!dossier.description?.length">Aucune description.</p>
          <div *ngIf="dossier.commentaire" class="commentaire-block">
            <strong>Commentaire :</strong> {{ dossier.commentaire }}
          </div>

          <mat-divider></mat-divider>

          <div class="action-buttons">
            <button mat-raised-button type="button" (click)="showDevisForm = true" [disabled]="dossier.statut !== 'ouvert' || showDevisForm">
              <mat-icon>request_quote</mat-icon> Enregistrer un devis
            </button>
            <button mat-raised-button type="button" (click)="showFactureForm = true" [disabled]="dossier.statut !== 'ouvert' || showFactureForm">
              <mat-icon>receipt</mat-icon> Enregistrer une facture
            </button>
            <button mat-stroked-button type="button" *ngIf="dossier.statut === 'ouvert'" (click)="updateStatut('cloture')" [disabled]="actionLoading">
              <mat-icon>lock</mat-icon> Clôturer le dossier
            </button>
            <button mat-stroked-button type="button" *ngIf="dossier.statut === 'cloture'" (click)="updateStatut('ouvert')" [disabled]="actionLoading">
              <mat-icon>lock_open</mat-icon> Réouvrir le dossier
            </button>
            <button mat-stroked-button type="button" color="warn" *ngIf="dossier.statut === 'ouvert'" (click)="updateStatut('annule')" [disabled]="actionLoading">
              <mat-icon>cancel</mat-icon> Annuler le dossier
            </button>
          </div>

          <mat-divider></mat-divider>

          <h4>Devis</h4>
          <app-devis-form *ngIf="showDevisForm" [dt]="dt" [immat]="immat" [numero]="numero"
            [dossierDescription]="dossier.description || []"
            (devisCreated)="onDevisCreated($event)" (cancelled)="showDevisForm = false"></app-devis-form>
          <p class="empty-section" *ngIf="!dossier.devis?.length && !showDevisForm">Aucun devis enregistré.</p>
          <div class="item-list" *ngIf="dossier.devis?.length">
            <div class="item-row" *ngFor="let d of dossier.devis">
              <span class="item-date">{{ d.date_devis | date:'dd/MM/yyyy' }}</span>
              <span class="item-fournisseur">{{ d.fournisseur?.nom || d.id }}</span>
              <span class="item-montant">{{ d.montant | number:'1.2-2' }} €</span>
              <span class="devis-statut-badge" [ngClass]="'devis-statut-' + d.statut">{{ devisStatutLabel(d.statut) }}</span>
              <button mat-stroked-button type="button" *ngIf="d.statut === 'en_attente' && dossier.statut === 'ouvert'"
                (click)="openApprovalForm(d)" [disabled]="approvalLoading" class="approval-btn">
                <mat-icon>send</mat-icon> Envoyer pour approbation
              </button>
            </div>
            <!-- Inline approval form -->
            <div class="approval-form" *ngIf="approvalDevis">
              <mat-form-field appearance="outline" class="approval-email-field">
                <mat-label>Valideur</mat-label>
                <input matInput [formControl]="valideurSearchControl" [matAutocomplete]="valideurAuto"
                       placeholder="Rechercher un valideur…" (focus)="onValideurFocus()">
                <button mat-icon-button matSuffix type="button" (click)="toggleValideurPanel($event)" tabindex="-1">
                  <mat-icon>arrow_drop_down</mat-icon>
                </button>
                <mat-autocomplete #valideurAuto="matAutocomplete" [displayWith]="displayValideurFn" (optionSelected)="onValideurSelected($event.option.value)">
                  <mat-option *ngFor="let v of filteredValideurs$ | async" [value]="v">
                    {{ v.nom }} <span class="valideur-hint"> — {{ v.email }}</span>
                  </mat-option>
                </mat-autocomplete>
              </mat-form-field>
              <button mat-raised-button color="primary" type="button" (click)="sendForApproval()" [disabled]="approvalLoading || !approvalEmail">
                <mat-icon>send</mat-icon> Envoyer
              </button>
              <button mat-button type="button" (click)="approvalDevis = null">Annuler</button>
            </div>
          </div>

          <h4>Factures</h4>
          <app-facture-form *ngIf="showFactureForm" [dt]="dt" [immat]="immat" [numero]="numero"
            [devisList]="dossier.devis || []"
            (factureCreated)="onFactureCreated($event)" (cancelled)="showFactureForm = false"></app-facture-form>
          <p class="empty-section" *ngIf="!dossier.factures?.length && !showFactureForm">Aucune facture enregistrée.</p>
          <div class="item-list" *ngIf="dossier.factures?.length">
            <div class="item-row" *ngFor="let f of dossier.factures">
              <span class="item-date">{{ f.date_facture | date:'dd/MM/yyyy' }}</span>
              <span class="item-fournisseur">{{ f.fournisseur?.nom || f.id }}</span>
              <span class="item-classification">{{ classificationLabel(f.classification) }}</span>
              <span class="item-montant">{{ f.montant_total | number:'1.2-2' }} €</span>
              <span class="item-montant-crf">CRF: {{ f.montant_crf | number:'1.2-2' }} €</span>
            </div>
          </div>
          <mat-divider></mat-divider>

          <h4>Historique</h4>
          <div class="timeline" *ngIf="historique.length">
            <div class="timeline-entry" *ngFor="let entry of historique">
              <mat-icon [ngClass]="'timeline-icon timeline-icon-' + entry.action"
                >{{ actionIcon(entry.action) }}</mat-icon>
              <div class="timeline-content">
                <span class="timeline-date">{{ entry.date | date:'dd/MM/yyyy HH:mm' }}</span>
                <span class="timeline-details">{{ entry.details }}</span>
                <span class="timeline-auteur">par {{ entry.auteur }}</span>
              </div>
            </div>
          </div>
          <p class="empty-section" *ngIf="!historique.length && !historiqueLoading">Aucun historique.</p>
          <mat-spinner diameter="20" *ngIf="historiqueLoading"></mat-spinner>
        </mat-card-content>
      </mat-card>
    </div>

    <div *ngIf="loading" class="loading-container">
      <mat-spinner diameter="32"></mat-spinner>
      <span>Chargement du dossier…</span>
    </div>
  `,
  styles: [`
    .detail-header { margin-bottom: 12px; }
    .dossier-header-row { margin-bottom: 8px; }
    .dossier-header-inline { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .header-separator { color: rgba(0,0,0,0.38); }
    .header-date { font-size: 14px; font-weight: 400; color: rgba(0,0,0,0.54); }
    .statut-badge { display: inline-block; padding: 4px 12px; border-radius: 16px; font-size: 12px; font-weight: 500; text-transform: uppercase; }
    .statut-ouvert { background: #e8f5e9; color: #2e7d32; }
    .statut-cloture { background: #eeeeee; color: #616161; }
    .statut-annule { background: #ffebee; color: #c62828; }
    .description-list { margin: 8px 0 16px; padding-left: 20px; }
    .description-list li { margin-bottom: 4px; }
    .commentaire-block { margin: 8px 0 16px; padding: 8px 12px; background: #f5f5f5; border-radius: 4px; font-style: italic; }
    .action-buttons { display: flex; gap: 12px; margin: 16px 0; flex-wrap: wrap; }
    .empty-section { color: rgba(0,0,0,0.54); font-style: italic; }
    .loading-container { display: flex; align-items: center; gap: 12px; padding: 24px 0; }
    h4 { margin: 16px 0 8px; font-weight: 500; }
    .item-list { margin: 8px 0 16px; }
    .item-row { display: flex; gap: 12px; align-items: center; padding: 8px 0; border-bottom: 1px solid rgba(0,0,0,0.08); flex-wrap: wrap; }
    .item-date { min-width: 90px; }
    .item-fournisseur { flex: 1; min-width: 120px; }
    .item-montant { font-weight: 500; }
    .item-montant-crf { color: rgba(0,0,0,0.54); }
    .item-classification { font-size: 12px; color: rgba(0,0,0,0.54); }
    .devis-statut-badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 500; text-transform: uppercase; }
    .devis-statut-en_attente { background: #fff9c4; color: #f9a825; }
    .devis-statut-envoye { background: #e3f2fd; color: #1565c0; }
    .devis-statut-approuve { background: #e8f5e9; color: #2e7d32; }
    .devis-statut-refuse { background: #ffebee; color: #c62828; }
    .devis-statut-annule { background: #eeeeee; color: #616161; }
    .approval-btn { margin-left: auto; }
    .approval-form { display: flex; align-items: center; gap: 12px; padding: 12px 0; flex-wrap: wrap; }
    .approval-email-field { min-width: 280px; }
    .valideur-hint { font-size: 12px; color: rgba(0,0,0,0.54); }
    .timeline { margin: 8px 0 16px; }
    .timeline-entry { display: flex; gap: 12px; align-items: flex-start; padding: 8px 0; border-left: 2px solid rgba(0,0,0,0.12); margin-left: 12px; padding-left: 16px; position: relative; }
    .timeline-entry::before { content: ''; position: absolute; left: -5px; top: 12px; width: 8px; height: 8px; border-radius: 50%; background: #bdbdbd; }
    .timeline-icon { font-size: 20px; width: 20px; height: 20px; flex-shrink: 0; }
    .timeline-icon-creation { color: #2e7d32; }
    .timeline-icon-cloture { color: #757575; }
    .timeline-icon-reouverture { color: #1565c0; }
    .timeline-icon-annulation { color: #c62828; }
    .timeline-icon-devis_ajoute, .timeline-icon-devis_modifie { color: #1565c0; }
    .timeline-icon-devis_envoye_approbation { color: #ef6c00; }
    .timeline-icon-devis_approuve { color: #2e7d32; }
    .timeline-icon-devis_refuse, .timeline-icon-devis_annule { color: #c62828; }
    .timeline-icon-facture_ajoutee, .timeline-icon-facture_modifiee { color: #1565c0; }
    .timeline-icon-modification { color: #1565c0; }
    .timeline-content { display: flex; flex-direction: column; gap: 2px; }
    .timeline-date { font-size: 12px; color: rgba(0,0,0,0.54); }
    .timeline-details { font-size: 14px; }
    .timeline-auteur { font-size: 12px; color: rgba(0,0,0,0.54); }
  `],
})
export class DossierDetailComponent implements OnInit, OnChanges {
  @Input() dt!: string;
  @Input() immat!: string;
  @Input() numero!: string;
  @Output() back = new EventEmitter<void>();

  private readonly repairService = inject(RepairService);
  private readonly valideurService = inject(ValideurService);
  private readonly snackBar = inject(MatSnackBar);
  private readonly cdr = inject(ChangeDetectorRef);

  @ViewChild(MatAutocompleteTrigger) valideurAutoTrigger!: MatAutocompleteTrigger;

  dossier: DossierReparation | null = null;
  loading = false;
  actionLoading = false;
  showDevisForm = false;
  showFactureForm = false;
  approvalDevis: Devis | null = null;
  approvalEmail = '';
  approvalLoading = false;
  historique: AuditEntry[] = [];
  historiqueLoading = false;

  // Valideur selector
  valideurSearchControl = new FormControl('');
  valideurs: Valideur[] = [];
  filteredValideurs$!: Observable<Valideur[]>;

  ngOnInit(): void {
    this.loadDossier();
    this.loadHistorique();
    this.loadValideurs();
    this.filteredValideurs$ = this.valideurSearchControl.valueChanges.pipe(
      startWith(''),
      map(value => {
        const searchStr = typeof value === 'string' ? value : (value as any)?.nom || '';
        return this.filterValideurs(searchStr);
      })
    );
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['numero'] && !changes['numero'].firstChange) {
      this.loadDossier();
    }
  }

  loadHistorique(): void {
    if (!this.dt || !this.immat || !this.numero) return;
    this.historiqueLoading = true;
    this.repairService.getHistorique(this.dt, this.immat, this.numero).subscribe({
      next: (entries) => { this.historique = entries; this.historiqueLoading = false; this.cdr.detectChanges(); },
      error: () => { this.historiqueLoading = false; this.cdr.detectChanges(); },
    });
  }

  actionIcon(action: string): string {
    const icons: Record<string, string> = {
      creation: 'add_circle',
      cloture: 'lock',
      reouverture: 'lock_open',
      annulation: 'cancel',
      modification: 'edit',
      devis_ajoute: 'description',
      devis_modifie: 'description',
      devis_envoye_approbation: 'send',
      devis_approuve: 'check_circle',
      devis_refuse: 'block',
      devis_annule: 'block',
      facture_ajoutee: 'receipt',
      facture_modifiee: 'receipt',
    };
    return icons[action] || 'info';
  }

  loadDossier(): void {
    if (!this.dt || !this.immat || !this.numero) return;
    this.loading = true;
    this.repairService.getDossier(this.dt, this.immat, this.numero).subscribe({
      next: (d) => { this.dossier = d; this.loading = false; this.cdr.detectChanges(); },
      error: () => {
        this.snackBar.open('Erreur lors du chargement du dossier', 'Fermer', { duration: 5000 });
        this.loading = false;
        this.cdr.detectChanges();
      },
    });
  }

  updateStatut(statut: 'ouvert' | 'cloture' | 'annule'): void {
    if (!this.dossier) return;
    this.actionLoading = true;
    this.repairService.updateDossier(this.dt, this.immat, this.dossier.numero, { statut }).subscribe({
      next: (d) => {
        this.dossier = d;
        this.actionLoading = false;
        this.snackBar.open('Statut mis à jour', 'Fermer', { duration: 3000 });
        this.cdr.detectChanges();
        this.loadHistorique();
      },
      error: () => {
        this.actionLoading = false;
        this.snackBar.open('Erreur lors de la mise à jour du statut', 'Fermer', { duration: 5000 });
        this.cdr.detectChanges();
      },
    });
  }

  statutLabel(statut: string): string {
    switch (statut) {
      case 'ouvert': return 'Ouvert';
      case 'cloture': return 'Clôturé';
      case 'annule': return 'Annulé';
      default: return statut;
    }
  }

  devisStatutLabel(statut: string): string {
    switch (statut) {
      case 'en_attente': return 'En attente';
      case 'envoye': return 'Envoyé';
      case 'approuve': return 'Approuvé';
      case 'refuse': return 'Refusé';
      case 'annule': return 'Annulé';
      default: return statut;
    }
  }

  classificationLabel(classification: string): string {
    const labels: Record<string, string> = {
      entretien_courant: 'Entretien courant',
      reparation_carrosserie_mecanique: 'Carrosserie / mécanique',
      reparation_sanitaire: 'Sanitaire',
      reparation_marquage: 'Marquage',
      controle_technique: 'Contrôle technique',
      frais_duplicata_carte_grise: 'Duplicata carte grise',
      autre: 'Autre',
    };
    return labels[classification] || classification;
  }

  onDevisCreated(_devis: Devis): void {
    this.showDevisForm = false;
    this.loadDossier();
    this.loadHistorique();
  }

  onFactureCreated(_facture: FactureCreateResponse): void {
    this.showFactureForm = false;
    this.loadDossier();
    this.loadHistorique();
  }

  private loadValideurs(): void {
    if (!this.dt) return;
    this.valideurService.listValideurs(this.dt).subscribe({
      next: (res) => {
        this.valideurs = (res.valideurs || []).filter(v => v.actif);
        this.cdr.detectChanges();
      },
    });
  }

  private filterValideurs(search: string): Valideur[] {
    if (!search) return this.valideurs;
    const lower = search.toLowerCase();
    return this.valideurs.filter(v =>
      v.nom.toLowerCase().includes(lower) || v.email.toLowerCase().includes(lower)
    );
  }

  displayValideurFn(valideur: Valideur | string): string {
    if (!valideur) return '';
    if (typeof valideur === 'string') return valideur;
    return valideur.nom;
  }

  onValideurSelected(valideur: Valideur): void {
    this.approvalEmail = valideur.email;
  }

  onValideurFocus(): void {
    if (!this.valideurSearchControl.value || this.valideurSearchControl.value === '') {
      this.valideurSearchControl.setValue('');
      setTimeout(() => this.valideurAutoTrigger?.openPanel());
    }
  }

  toggleValideurPanel(event: Event): void {
    event.stopPropagation();
    if (this.valideurAutoTrigger.panelOpen) {
      this.valideurAutoTrigger.closePanel();
    } else {
      this.valideurSearchControl.setValue('');
      this.valideurAutoTrigger.openPanel();
    }
  }

  openApprovalForm(devis: Devis): void {
    this.approvalDevis = devis;
    this.approvalEmail = '';
    this.valideurSearchControl.setValue('');
  }

  sendForApproval(): void {
    if (!this.approvalDevis || !this.approvalEmail || !this.dossier) return;
    this.approvalLoading = true;
    this.repairService.sendApproval(
      this.dt, this.immat, this.dossier.numero,
      String(this.approvalDevis.id),
      { valideur_email: this.approvalEmail }
    ).subscribe({
      next: () => {
        this.approvalLoading = false;
        this.approvalDevis = null;
        this.snackBar.open('Devis envoyé pour approbation', 'Fermer', { duration: 5000 });
        this.cdr.detectChanges();
        this.loadDossier();
      },
      error: () => {
        this.approvalLoading = false;
        this.snackBar.open('Erreur lors de l\'envoi pour approbation', 'Fermer', { duration: 5000 });
        this.cdr.detectChanges();
      },
    });
  }
}

