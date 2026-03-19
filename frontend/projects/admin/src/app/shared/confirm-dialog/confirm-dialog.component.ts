import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

export interface ConfirmDialogData {
  title: string;
  message: string;       // Main message (HTML supported via [innerHTML])
  confirmLabel?: string;  // Default: 'Confirmer'
  cancelLabel?: string;   // Default: 'Annuler'
  confirmColor?: 'primary' | 'accent' | 'warn';  // Default: 'warn'
  icon?: string;          // Material icon name, default: 'warning'
}

@Component({
  selector: 'app-confirm-dialog',
  standalone: true,
  imports: [CommonModule, MatDialogModule, MatButtonModule, MatIconModule],
  template: `
    <h2 mat-dialog-title>
      <mat-icon [class]="'dialog-icon ' + (data.confirmColor || 'warn')">{{ data.icon || 'warning' }}</mat-icon>
      {{ data.title }}
    </h2>
    <mat-dialog-content>
      <div [innerHTML]="data.message"></div>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button (click)="dialogRef.close(false)">{{ data.cancelLabel || 'Annuler' }}</button>
      <button mat-raised-button [color]="data.confirmColor || 'warn'" (click)="dialogRef.close(true)">
        {{ data.confirmLabel || 'Confirmer' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    .dialog-icon {
      vertical-align: middle;
      margin-right: 8px;
    }
    .dialog-icon.warn { color: #f44336; }
    .dialog-icon.primary { color: #1976d2; }
    .dialog-icon.accent { color: #ff4081; }
    mat-dialog-content {
      min-width: 400px;
      padding: 16px 24px;
      line-height: 1.6;
    }
    h2[mat-dialog-title] {
      display: flex;
      align-items: center;
    }
  `]
})
export class ConfirmDialogComponent {
  data = inject<ConfirmDialogData>(MAT_DIALOG_DATA);
  dialogRef = inject(MatDialogRef<ConfirmDialogComponent>);
}

