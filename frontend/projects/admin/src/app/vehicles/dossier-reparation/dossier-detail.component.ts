import { Component, Input, Output, EventEmitter, OnInit, OnChanges, SimpleChanges, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
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
import { RepairService } from '../../services/repair.service';
import { DossierReparation, Devis, FactureCreateResponse, AuditEntry } from '../../models/repair.model';
import { DevisFormComponent } from './devis-form.component';
import { FactureFormComponent } from './facture-form.component';

@Component({
  selector: 'app-dossier-detail',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
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
    DevisFormComponent,
    FactureFormComponent,
  ],
  template: `
    <div class="dossier-detail" *ngIf="!loading && dossier">
      <div class="detail-header">
        <button mat-button type="button" (click)="back.emit()"><mat-icon>arrow_back</mat-icon> Retour à la liste</button>
      </div>

      <mat-card>
        <mat-card-header>
          <mat-card-title>{{ dossier.numero }}</mat-card-title>
          <mat-card-subtitle>Créé le {{ dossier.date_creation | date:'dd/MM/yyyy HH:mm' }}</mat-card-subtitle>
        </mat-card-header>
        <mat-card-content>
          <div class="status-row">
            <span class="statut-badge" [ngClass]="'statut-' + dossier.statut">{{ statutLabel(dossier.statut) }}</span>
          </div>

          <h4>Description</h4>
          <p class="description-text">{{ dossier.description }}</p>

          <mat-divider></mat-divider>

          <div class="action-buttons">
            <button mat-raised-button type="button" (click)="showDevisForm = true" [disabled]="dossier.statut !== 'ouvert' || showDevisForm">
              <mat-icon>request_quote</mat-icon> Enregistrer un devis
            </button>
            <button mat-raised-button type="button" (click)="showFactureForm = true" [disabled]="dossier.statut !== 'ouvert' || showFactureForm">
              <mat-icon>receipt</mat-icon> Enregistrer une facture
            </button>
          </div>

          <div class="action-buttons">
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
            (devisCreated)="onDevisCreated($event)" (cancelled)="showDevisForm = false"></app-devis-form>
          <p class="empty-section" *ngIf="!dossier.devis?.length && !showDevisForm">Aucun devis enregistré.</p>
          <div class="item-list" *ngIf="dossier.devis?.length">
            <div class="item-row" *ngFor="let d of dossier.devis">
              <span class="item-date">{{ d.date_devis | date:'dd/MM/yyyy' }}</span>
              <span class="item-fournisseur">{{ d.fournisseur_nom || d.fournisseur_id }}</span>
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
                <mat-label>Email du valideur</mat-label>
                <input matInput [(ngModel)]="approvalEmail" type="email" placeholder="chef@croix-rouge.fr">
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
              <span class="item-fournisseur">{{ f.fournisseur_nom || f.fournisseur_id }}</span>
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
    .status-row { margin-bottom: 16px; }
    .statut-badge { display: inline-block; padding: 4px 12px; border-radius: 16px; font-size: 12px; font-weight: 500; text-transform: uppercase; }
    .statut-ouvert { background: #e8f5e9; color: #2e7d32; }
    .statut-cloture { background: #eeeeee; color: #616161; }
    .statut-annule { background: #ffebee; color: #c62828; }
    .description-text { white-space: pre-wrap; margin: 8px 0 16px; }
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
  private readonly snackBar = inject(MatSnackBar);

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

  ngOnInit(): void { this.loadDossier(); this.loadHistorique(); }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['numero'] && !changes['numero'].firstChange) {
      this.loadDossier();
    }
  }

  loadHistorique(): void {
    if (!this.dt || !this.immat || !this.numero) return;
    this.historiqueLoading = true;
    this.repairService.getHistorique(this.dt, this.immat, this.numero).subscribe({
      next: (entries) => { this.historique = entries; this.historiqueLoading = false; },
      error: () => { this.historiqueLoading = false; },
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
      next: (d) => { this.dossier = d; this.loading = false; },
      error: () => {
        this.snackBar.open('Erreur lors du chargement du dossier', 'Fermer', { duration: 5000 });
        this.loading = false;
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
        this.loadHistorique();
      },
      error: () => {
        this.actionLoading = false;
        this.snackBar.open('Erreur lors de la mise à jour du statut', 'Fermer', { duration: 5000 });
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

  openApprovalForm(devis: Devis): void {
    this.approvalDevis = devis;
    this.approvalEmail = '';
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
        this.loadDossier();
      },
      error: () => {
        this.approvalLoading = false;
        this.snackBar.open('Erreur lors de l\'envoi pour approbation', 'Fermer', { duration: 5000 });
      },
    });
  }
}

