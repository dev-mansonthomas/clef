import { Component, Input, Output, EventEmitter, OnInit, OnChanges, SimpleChanges, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { RepairService } from '../../services/repair.service';
import { DossierReparation } from '../../models/repair.model';

@Component({
  selector: 'app-dossier-list',
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatChipsModule,
    MatProgressSpinnerModule,
  ],
  template: `
    <div class="dossier-list">
      <div class="dossier-list-header">
        <h3>Dossiers de réparation</h3>
        <button mat-raised-button color="primary" (click)="showCreate.emit()">
          <mat-icon>add</mat-icon> Nouveau Dossier Réparation
        </button>
      </div>

      <div *ngIf="loading" class="loading-container">
        <mat-spinner diameter="32"></mat-spinner>
        <span>Chargement des dossiers…</span>
      </div>

      <div *ngIf="!loading && dossiers.length === 0" class="empty-state">
        <mat-icon>inbox</mat-icon>
        <p>Aucun dossier de réparation pour ce véhicule.</p>
      </div>

      <mat-card *ngFor="let d of dossiers" class="dossier-card" (click)="dossierSelected.emit(d.numero)">
        <mat-card-header>
          <mat-card-title>{{ d.numero }}</mat-card-title>
          <mat-card-subtitle>{{ d.date_creation | date:'dd/MM/yyyy' }}</mat-card-subtitle>
        </mat-card-header>
        <mat-card-content>
          <p class="dossier-description">{{ truncate(d.description, 80) }}</p>
          <div class="dossier-meta">
            <span class="statut-badge" [ngClass]="'statut-' + d.statut">{{ statutLabel(d.statut) }}</span>
            <span class="counts" *ngIf="d.devis?.length || d.factures?.length">
              <span *ngIf="d.devis?.length"><mat-icon class="small-icon">request_quote</mat-icon> {{ d.devis.length }} devis</span>
              <span *ngIf="d.factures?.length"><mat-icon class="small-icon">receipt</mat-icon> {{ d.factures.length }} factures</span>
            </span>
          </div>
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: [`
    .dossier-list-header {
      display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 12px;
      h3 { margin: 0; font-size: 20px; font-weight: 500; }
    }
    .loading-container { display: flex; align-items: center; gap: 12px; padding: 24px 0; }
    .empty-state { text-align: center; padding: 48px 16px; color: rgba(0,0,0,0.54);
      mat-icon { font-size: 48px; width: 48px; height: 48px; }
    }
    .dossier-card { margin-bottom: 12px; cursor: pointer; transition: box-shadow 0.2s; }
    .dossier-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
    .dossier-description { margin: 8px 0; color: rgba(0,0,0,0.7); }
    .dossier-meta { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
    .statut-badge {
      display: inline-block; padding: 4px 12px; border-radius: 16px; font-size: 12px; font-weight: 500; text-transform: uppercase;
    }
    .statut-ouvert { background: #e8f5e9; color: #2e7d32; }
    .statut-cloture { background: #eeeeee; color: #616161; }
    .statut-annule { background: #ffebee; color: #c62828; }
    .counts { display: flex; gap: 12px; align-items: center; font-size: 13px; color: rgba(0,0,0,0.6); }
    .small-icon { font-size: 16px; width: 16px; height: 16px; vertical-align: middle; margin-right: 2px; }
  `],
})
export class DossierListComponent implements OnInit, OnChanges {
  @Input() dt!: string;
  @Input() immat!: string;
  @Input() refreshTrigger = 0;
  @Output() dossierSelected = new EventEmitter<string>();
  @Output() showCreate = new EventEmitter<void>();

  private readonly repairService = inject(RepairService);
  dossiers: DossierReparation[] = [];
  loading = false;

  ngOnInit(): void {
    this.loadDossiers();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['refreshTrigger'] && !changes['refreshTrigger'].firstChange) {
      this.loadDossiers();
    }
  }

  loadDossiers(): void {
    if (!this.dt || !this.immat) return;
    this.loading = true;
    this.repairService.listDossiers(this.dt, this.immat).subscribe({
      next: (res) => {
        this.dossiers = (res.dossiers || []).sort((a, b) =>
          new Date(b.date_creation).getTime() - new Date(a.date_creation).getTime()
        );
        this.loading = false;
      },
      error: () => { this.loading = false; },
    });
  }

  truncate(text: string, max: number): string {
    return text && text.length > max ? text.substring(0, max) + '…' : text;
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

