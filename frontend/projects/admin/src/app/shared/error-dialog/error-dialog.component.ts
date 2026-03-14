import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatExpansionModule } from '@angular/material/expansion';

export interface ErrorDialogData {
  userMessage: string;
  technicalDetails?: any;
}

@Component({
  selector: 'app-error-dialog',
  standalone: true,
  imports: [CommonModule, MatDialogModule, MatButtonModule, MatExpansionModule],
  template: `
    <h2 mat-dialog-title>❌ Une erreur est survenue</h2>
    <mat-dialog-content>
      <p class="user-message">{{ data.userMessage }}</p>
      
      <mat-expansion-panel *ngIf="data.technicalDetails">
        <mat-expansion-panel-header>
          <mat-panel-title>Détails techniques</mat-panel-title>
        </mat-expansion-panel-header>
        <pre class="technical-details">{{ data.technicalDetails | json }}</pre>
      </mat-expansion-panel>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-raised-button mat-dialog-close color="primary">Fermer</button>
    </mat-dialog-actions>
  `,
  styles: [`
    .user-message { font-size: 16px; margin-bottom: 16px; }
    .technical-details { 
      background: #f5f5f5; 
      padding: 12px; 
      font-size: 12px;
      overflow-x: auto;
      white-space: pre-wrap;
    }
    mat-expansion-panel { margin-top: 16px; }
  `]
})
export class ErrorDialogComponent {
  data = inject<ErrorDialogData>(MAT_DIALOG_DATA);
}

