import { Component, Input, OnInit, OnChanges, SimpleChanges, inject, ViewChild, ElementRef, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTableModule } from '@angular/material/table';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Router } from '@angular/router';
import { Chart, registerables } from 'chart.js';
import { RepairService } from '../../services/repair.service';
import { DepensesResponse, DepenseYear, DepenseFacture } from '../../models/repair.model';

Chart.register(...registerables);

const CLASSIFICATION_LABELS: Record<string, string> = {
  entretien_courant: 'Entretien courant',
  reparation_carrosserie: 'Réparation carrosserie/mécanique',
  reparation_sanitaire: 'Réparation sanitaire',
  reparation_marquage: 'Réparation marquage',
  controle_technique: 'Contrôle technique',
  frais_duplicata_cg: 'Frais duplicata carte grise',
  autre: 'Autre',
};

@Component({
  selector: 'app-depenses-tab',
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatTableModule,
    MatTooltipModule,
  ],
  template: `
    <div class="depenses-container">
      <div *ngIf="loading" class="loading-container">
        <mat-spinner diameter="40"></mat-spinner>
        <p>Chargement des dépenses...</p>
      </div>

      <div *ngIf="!loading && depenses">
        <!-- Summary header -->
        <mat-card class="summary-card">
          <mat-card-content>
            <div class="summary-row">
              <div class="summary-item">
                <span class="summary-label">Total dossiers</span>
                <span class="summary-value">{{ totalDossiers }}</span>
              </div>
              <div class="summary-item">
                <span class="summary-label">Total coûts</span>
                <span class="summary-value">{{ depenses.total_all_years_cout | number:'1.2-2' }} €</span>
              </div>
              <div class="summary-item">
                <span class="summary-label">Total CRF</span>
                <span class="summary-value">{{ depenses.total_all_years_crf | number:'1.2-2' }} €</span>
              </div>
              <div class="summary-actions">
                <button mat-stroked-button (click)="exportCsv()"><mat-icon>download</mat-icon> Export CSV</button>
                <button mat-stroked-button (click)="exportPdf()"><mat-icon>picture_as_pdf</mat-icon> Export PDF</button>
              </div>
            </div>
          </mat-card-content>
        </mat-card>

        <!-- Chart -->
        <mat-card class="chart-card" *ngIf="depenses.years.length > 0">
          <mat-card-header><mat-card-title>Accumulation des coûts</mat-card-title></mat-card-header>
          <mat-card-content>
            <div class="chart-wrapper"><canvas #chartCanvas></canvas></div>
          </mat-card-content>
        </mat-card>

        <!-- Table grouped by year -->
        <div *ngIf="depenses.years.length === 0" class="empty-state">
          <mat-icon>receipt_long</mat-icon>
          <p>Aucune dépense enregistrée pour ce véhicule.</p>
        </div>

        <div *ngFor="let yearData of depenses.years" class="year-group">
          <mat-card>
            <mat-card-header>
              <mat-card-title>{{ yearData.year }}</mat-card-title>
              <mat-card-subtitle>{{ yearData.nb_dossiers }} dossier(s) — {{ yearData.total_cout | number:'1.2-2' }} € total — {{ yearData.total_crf | number:'1.2-2' }} € CRF</mat-card-subtitle>
            </mat-card-header>
            <mat-card-content>
              <table mat-table [dataSource]="yearData.factures" class="depenses-table">
                <ng-container matColumnDef="date">
                  <th mat-header-cell *matHeaderCellDef>Date</th>
                  <td mat-cell *matCellDef="let f">{{ f.date | date:'dd/MM/yyyy' }}</td>
                </ng-container>
                <ng-container matColumnDef="numero_dossier">
                  <th mat-header-cell *matHeaderCellDef>N° Dossier</th>
                  <td mat-cell *matCellDef="let f"><a class="dossier-link" (click)="navigateToDossier(f.numero_dossier)">{{ f.numero_dossier }}</a></td>
                </ng-container>
                <ng-container matColumnDef="fournisseur">
                  <th mat-header-cell *matHeaderCellDef>Fournisseur</th>
                  <td mat-cell *matCellDef="let f">{{ f.fournisseur_nom }}</td>
                </ng-container>
                <ng-container matColumnDef="classification">
                  <th mat-header-cell *matHeaderCellDef>Classification</th>
                  <td mat-cell *matCellDef="let f">{{ getClassificationLabel(f.classification) }}</td>
                </ng-container>
                <ng-container matColumnDef="montant_total">
                  <th mat-header-cell *matHeaderCellDef>Coût Total</th>
                  <td mat-cell *matCellDef="let f">{{ f.montant_total | number:'1.2-2' }} €</td>
                </ng-container>
                <ng-container matColumnDef="montant_crf">
                  <th mat-header-cell *matHeaderCellDef>Coût CRF</th>
                  <td mat-cell *matCellDef="let f">{{ f.montant_crf | number:'1.2-2' }} €</td>
                </ng-container>
                <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
                <tr mat-row *matRowDef="let row; columns: displayedColumns;"></tr>
              </table>
            </mat-card-content>
          </mat-card>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .depenses-container { padding: 0; }
    .loading-container { display: flex; flex-direction: column; align-items: center; padding: 48px 0; gap: 16px; }
    .summary-card { margin-bottom: 24px; }
    .summary-row { display: flex; align-items: center; gap: 32px; flex-wrap: wrap; }
    .summary-item { display: flex; flex-direction: column; }
    .summary-label { font-size: 12px; color: rgba(0,0,0,0.6); text-transform: uppercase; }
    .summary-value { font-size: 24px; font-weight: 500; }
    .summary-actions { margin-left: auto; display: flex; gap: 8px; }
    .chart-card { margin-bottom: 24px; }
    .chart-wrapper { max-height: 300px; position: relative; }
    .year-group { margin-bottom: 16px; }
    .depenses-table { width: 100%; }
    .dossier-link { color: #1976d2; cursor: pointer; text-decoration: underline; }
    .empty-state { display: flex; flex-direction: column; align-items: center; padding: 48px; color: rgba(0,0,0,0.5); }
    .empty-state mat-icon { font-size: 48px; width: 48px; height: 48px; margin-bottom: 16px; }
  `]
})
export class DepensesTabComponent implements OnInit, OnChanges {
  @Input() dt = '';
  @Input() immat = '';
  @ViewChild('chartCanvas') chartCanvas!: ElementRef<HTMLCanvasElement>;



  private readonly repairService = inject(RepairService);
  private readonly router = inject(Router);
  private readonly cdr = inject(ChangeDetectorRef);

  loading = false;
  depenses: DepensesResponse | null = null;
  totalDossiers = 0;
  displayedColumns = ['date', 'numero_dossier', 'fournisseur', 'classification', 'montant_total', 'montant_crf'];
  private chart: Chart | null = null;

  ngOnInit(): void {
    this.loadDepenses();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if ((changes['dt'] || changes['immat']) && !changes['dt']?.firstChange) {
      this.loadDepenses();
    }
  }

  private loadDepenses(): void {
    if (!this.dt || !this.immat) return;
    this.loading = true;
    this.repairService.getDepenses(this.dt, this.immat).subscribe({
      next: (data) => {
        this.depenses = data;
        this.totalDossiers = data.years.reduce((sum, y) => sum + y.nb_dossiers, 0);
        this.loading = false;
        this.cdr.detectChanges();
        setTimeout(() => this.buildChart(), 100);
      },
      error: () => {
        this.loading = false;
        this.cdr.detectChanges();
      },
    });
  }

  private buildChart(): void {
    if (!this.depenses || !this.chartCanvas?.nativeElement) return;
    if (this.chart) { this.chart.destroy(); }

    const years = [...this.depenses.years].sort((a, b) => a.year - b.year);
    const datasets: any[] = [];
    const colors = ['#E30613', '#1976d2', '#388e3c', '#f57c00', '#7b1fa2'];
    const months = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc'];

    years.forEach((yearData, i) => {
      const monthlyAccum = new Array(12).fill(0);
      yearData.factures.forEach(f => {
        const month = new Date(f.date).getMonth();
        monthlyAccum[month] += f.montant_total;
      });
      for (let m = 1; m < 12; m++) {
        monthlyAccum[m] += monthlyAccum[m - 1];
      }
      datasets.push({
        label: `${yearData.year}`,
        data: monthlyAccum,
        borderColor: colors[i % colors.length],
        backgroundColor: 'transparent',
        tension: 0.3,
      });
    });

    this.chart = new Chart(this.chartCanvas.nativeElement, {
      type: 'line',
      data: { labels: months, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'top' } },
        scales: { y: { beginAtZero: true, ticks: { callback: (v) => `${v} €` } } },
      },
    });
  }

  getClassificationLabel(classification: string): string {
    return CLASSIFICATION_LABELS[classification] || classification;
  }

  navigateToDossier(numero: string): void {
    console.log('Navigate to dossier:', numero);
  }

  exportCsv(): void {
    this.repairService.exportDepenses(this.dt, this.immat, 'csv').subscribe(blob => {
      this.downloadBlob(blob, `depenses-${this.immat}.csv`);
    });
  }

  exportPdf(): void {
    this.repairService.exportDepenses(this.dt, this.immat, 'pdf').subscribe(blob => {
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
    });
  }

  private downloadBlob(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }
}
