import { Component, Input, Output, EventEmitter, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatTableModule } from '@angular/material/table';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

/**
 * Import Configuration Component
 * 
 * Allows user to:
 * - Configure number of lines to skip
 * - Preview first 5 lines of data
 */
@Component({
  selector: 'app-import-config',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatTableModule,
    MatProgressSpinnerModule
  ],
  template: `
    <div class="config-container">
      <h3>Configuration de l'import</h3>
      
      <mat-form-field appearance="outline">
        <mat-label>Ignorer les premières lignes</mat-label>
        <input
          matInput
          type="number"
          min="0"
          max="50"
          [(ngModel)]="skipLinesValue"
          (ngModelChange)="onSkipLinesChange($event)"
        >
        <mat-hint>
          @if (skipLinesValue > 0) {
            Les lignes 1 à {{ skipLinesValue }} seront ignorées (en-têtes, titres, etc.)
          } @else {
            Aucune ligne ne sera ignorée
          }
        </mat-hint>
      </mat-form-field>
      
      <div class="preview-section">
        <h4>Aperçu des données</h4>
        
        @if (loading()) {
          <div class="loading">
            <mat-spinner diameter="40"></mat-spinner>
            <p>Chargement de l'aperçu...</p>
          </div>
        } @else if (previewData().length > 0) {
          <div class="table-container">
            <table mat-table [dataSource]="previewData()" class="preview-table">
              @for (column of displayedColumns(); track column; let i = $index) {
                <ng-container [matColumnDef]="column">
                  <th mat-header-cell *matHeaderCellDef>Colonne {{ i + 1 }}</th>
                  <td mat-cell *matCellDef="let row">{{ row[i] || '-' }}</td>
                </ng-container>
              }
              
              <tr mat-header-row *matHeaderRowDef="displayedColumns()"></tr>
              <tr mat-row *matRowDef="let row; columns: displayedColumns()"></tr>
            </table>
          </div>
          
          <p class="preview-info">
            Affichage des 5 premières lignes après avoir ignoré {{ skipLinesValue }} ligne(s)
          </p>
        } @else {
          <p class="no-data">Aucune donnée à afficher</p>
        }
      </div>
    </div>
  `,
  styles: [`
    .config-container {
      h3 {
        margin-bottom: 24px;
        color: var(--mat-sys-on-surface);
      }

      h4 {
        margin: 24px 0 16px;
        color: var(--mat-sys-on-surface-variant);
      }

      mat-form-field {
        width: 300px;
      }
    }

    .preview-section {
      margin-top: 32px;
    }

    .table-container {
      overflow-x: auto;
      border: 1px solid var(--mat-sys-outline-variant);
      border-radius: 8px;
      margin-bottom: 16px;
    }

    .preview-table {
      width: 100%;
      
      th {
        background-color: var(--mat-sys-surface-container);
        font-weight: 500;
      }
    }

    .preview-info {
      font-size: 14px;
      color: var(--mat-sys-on-surface-variant);
      margin: 8px 0;
    }

    .loading {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 16px;
      padding: 48px;
      
      p {
        color: var(--mat-sys-on-surface-variant);
      }
    }

    .no-data {
      text-align: center;
      padding: 48px;
      color: var(--mat-sys-on-surface-variant);
    }
  `]
})
export class ImportConfigComponent implements OnInit {
  @Input() file!: File;
  @Input() skipLines = 0;
  @Output() skipLinesChange = new EventEmitter<number>();

  skipLinesValue = 0;
  loading = signal(false);
  previewData = signal<string[][]>([]);
  displayedColumns = signal<string[]>([]);
  
  ngOnInit(): void {
    this.skipLinesValue = this.skipLines;
    this.loadPreview();
  }
  
  onSkipLinesChange(value: number): void {
    this.skipLinesChange.emit(value);
    this.loadPreview();
  }
  
  private async loadPreview(): Promise<void> {
    if (!this.file) return;
    
    this.loading.set(true);
    try {
      const text = await this.file.text();
      const lines = text.split('\n');
      
      // Skip configured lines and take next 5
      const dataLines = lines
        .slice(this.skipLinesValue, this.skipLinesValue + 5)
        .filter(line => line.trim().length > 0);
      
      // Parse CSV (simple split by comma - TODO: handle quoted values)
      const rows = dataLines.map(line => 
        line.split(',').map(cell => cell.trim())
      );
      
      if (rows.length > 0) {
        const columnCount = Math.max(...rows.map(r => r.length));
        this.displayedColumns.set(
          Array.from({ length: columnCount }, (_, i) => `col${i}`)
        );
      }
      
      this.previewData.set(rows);
    } catch (error) {
      console.error('Error loading preview:', error);
    } finally {
      this.loading.set(false);
    }
  }
}

