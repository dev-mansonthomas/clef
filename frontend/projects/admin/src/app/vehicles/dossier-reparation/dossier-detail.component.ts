import { Component, Input, Output, EventEmitter, OnInit, OnChanges, SimpleChanges, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatDividerModule } from '@angular/material/divider';
import { RepairService } from '../../services/repair.service';
import { DossierReparation } from '../../models/repair.model';

@Component({
  selector: 'app-dossier-detail',
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatChipsModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatDividerModule,
  ],
  template: `
    <div class="dossier-detail" *ngIf="!loading && dossier">
      <div class="detail-header">
        <button mat-button (click)="back.emit()"><mat-icon>arrow_back</mat-icon> Retour à la liste</button>
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
            <button mat-raised-button disabled matTooltip="Disponible dans une prochaine version">
              <mat-icon>request_quote</mat-icon> Enregistrer un devis
            </button>
            <button mat-raised-button disabled matTooltip="Disponible dans une prochaine version">
              <mat-icon>receipt</mat-icon> Enregistrer une facture
            </button>
          </div>

          <div class="action-buttons">
            <button mat-stroked-button *ngIf="dossier.statut === 'ouvert'" (click)="updateStatut('cloture')" [disabled]="actionLoading">
              <mat-icon>lock</mat-icon> Clôturer le dossier
            </button>
            <button mat-stroked-button *ngIf="dossier.statut === 'cloture'" (click)="updateStatut('ouvert')" [disabled]="actionLoading">
              <mat-icon>lock_open</mat-icon> Réouvrir le dossier
            </button>
            <button mat-stroked-button color="warn" *ngIf="dossier.statut === 'ouvert'" (click)="updateStatut('annule')" [disabled]="actionLoading">
              <mat-icon>cancel</mat-icon> Annuler le dossier
            </button>
          </div>

          <mat-divider></mat-divider>

          <h4>Devis</h4>
          <p class="empty-section" *ngIf="!dossier.devis?.length">Aucun devis enregistré.</p>

          <h4>Factures</h4>
          <p class="empty-section" *ngIf="!dossier.factures?.length">Aucune facture enregistrée.</p>
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

  ngOnInit(): void { this.loadDossier(); }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['numero'] && !changes['numero'].firstChange) {
      this.loadDossier();
    }
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
}

