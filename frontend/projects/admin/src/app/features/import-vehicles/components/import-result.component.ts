import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatTableModule } from '@angular/material/table';

interface ImportError {
  line_number: number;
  reason: string;
  values?: string[];
}

interface ImportResult {
  total_lines: number;
  ignored_lines: number;
  created: number;
  updated: number;
  errors: ImportError[];
}

/**
 * Import Result Component
 * 
 * Displays:
 * - Statistics (created, updated, ignored, errors)
 * - List of errors with line numbers
 * - Download report button
 */
@Component({
  selector: 'app-import-result',
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatIconModule,
    MatButtonModule,
    MatTableModule
  ],
  template: `
    <div class="result-container">
      @if (result) {
        <div class="success-header">
          <mat-icon class="success-icon">check_circle</mat-icon>
          <h3>Import terminé</h3>
        </div>
        
        <div class="stats-grid">
          <mat-card class="stat-card">
            <mat-card-content>
              <div class="stat-value">{{ result.total_lines }}</div>
              <div class="stat-label">Lignes traitées</div>
            </mat-card-content>
          </mat-card>

          <mat-card class="stat-card success">
            <mat-card-content>
              <div class="stat-value">{{ result.created }}</div>
              <div class="stat-label">Véhicules créés</div>
            </mat-card-content>
          </mat-card>

          <mat-card class="stat-card info">
            <mat-card-content>
              <div class="stat-value">{{ result.updated }}</div>
              <div class="stat-label">Véhicules mis à jour</div>
            </mat-card-content>
          </mat-card>

          <mat-card class="stat-card warning">
            <mat-card-content>
              <div class="stat-value">{{ result.ignored_lines }}</div>
              <div class="stat-label">Lignes ignorées</div>
            </mat-card-content>
          </mat-card>

          <mat-card class="stat-card error">
            <mat-card-content>
              <div class="stat-value">{{ result.errors.length }}</div>
              <div class="stat-label">Erreurs</div>
            </mat-card-content>
          </mat-card>
        </div>
        
        @if (result.errors.length > 0) {
          <div class="errors-section">
            <h4>
              <mat-icon>error</mat-icon>
              Erreurs rencontrées
            </h4>

            <div class="table-container">
              <table mat-table [dataSource]="result.errors" class="errors-table">
                <ng-container matColumnDef="line_number">
                  <th mat-header-cell *matHeaderCellDef>Ligne</th>
                  <td mat-cell *matCellDef="let error">{{ error.line_number }}</td>
                </ng-container>

                <ng-container matColumnDef="reason">
                  <th mat-header-cell *matHeaderCellDef>Raison</th>
                  <td mat-cell *matCellDef="let error">{{ error.reason }}</td>
                </ng-container>

                <tr mat-header-row *matHeaderRowDef="['line_number', 'reason']"></tr>
                <tr mat-row *matRowDef="let row; columns: ['line_number', 'reason']"></tr>
              </table>
            </div>
          </div>
        }
        
        <div class="actions">
          <button mat-raised-button (click)="downloadReport()">
            <mat-icon>download</mat-icon>
            Télécharger le rapport
          </button>
        </div>
      } @else {
        <div class="no-result">
          <mat-icon>info</mat-icon>
          <p>Aucun résultat d'import disponible</p>
        </div>
      }
    </div>
  `,
  styles: [`
    .result-container {
      padding: 24px 0;
    }

    .success-header {
      display: flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 32px;
      
      .success-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        color: var(--mat-sys-primary);
      }
      
      h3 {
        margin: 0;
        color: var(--mat-sys-on-surface);
      }
    }

    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 16px;
      margin-bottom: 32px;
    }

    .stat-card {
      text-align: center;
      
      mat-card-content {
        padding: 24px 16px;
      }
      
      .stat-value {
        font-size: 32px;
        font-weight: 500;
        margin-bottom: 8px;
      }
      
      .stat-label {
        font-size: 14px;
        color: var(--mat-sys-on-surface-variant);
      }
      
      &.success .stat-value {
        color: var(--mat-sys-primary);
      }
      
      &.info .stat-value {
        color: var(--mat-sys-tertiary);
      }
      
      &.warning .stat-value {
        color: #ff9800;
      }
      
      &.error .stat-value {
        color: var(--mat-sys-error);
      }
    }

    .errors-section {
      margin-bottom: 32px;
      
      h4 {
        display: flex;
        align-items: center;
        gap: 8px;
        color: var(--mat-sys-error);
        margin-bottom: 16px;
        
        mat-icon {
          font-size: 24px;
          width: 24px;
          height: 24px;
        }
      }
    }

    .table-container {
      border: 1px solid var(--mat-sys-outline-variant);
      border-radius: 8px;
      overflow: hidden;
    }

    .errors-table {
      width: 100%;
      
      th {
        background-color: var(--mat-sys-surface-container);
        font-weight: 500;
      }
    }

    .actions {
      display: flex;
      justify-content: center;
      gap: 16px;
      
      button {
        min-width: 200px;
      }
    }

    .no-result {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 16px;
      padding: 48px;
      
      mat-icon {
        font-size: 64px;
        width: 64px;
        height: 64px;
        color: var(--mat-sys-on-surface-variant);
      }
      
      p {
        color: var(--mat-sys-on-surface-variant);
        margin: 0;
      }
    }
  `]
})
export class ImportResultComponent {
  @Input() result: ImportResult | null = null;
  
  downloadReport(): void {
    if (!this.result) return;
    
    // Generate CSV report
    const lines = [
      'Rapport d\'import de véhicules',
      '',
      `Total lignes: ${this.result.total_lines}`,
      `Véhicules créés: ${this.result.created}`,
      `Véhicules mis à jour: ${this.result.updated}`,
      `Lignes ignorées: ${this.result.ignored_lines}`,
      `Erreurs: ${this.result.errors.length}`,
      '',
      'Détail des erreurs:',
      'Ligne,Raison',
      ...this.result.errors.map(e => `${e.line_number},"${e.reason}"`)
    ];
    
    const csv = lines.join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `rapport-import-${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }
}

