import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatDialogModule, MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';

@Component({
  selector: 'app-confirm-cancel-devis-dialog',
  standalone: true,
  imports: [CommonModule, MatDialogModule, MatButtonModule],
  template: `
    <h2 mat-dialog-title>Annuler le devis ?</h2>
    <mat-dialog-content>
      <p>{{ data.message }}</p>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button (click)="dialogRef.close(false)">Non, garder</button>
      <button mat-raised-button color="warn" (click)="dialogRef.close(true)">Annuler le devis</button>
    </mat-dialog-actions>
  `,
})
export class ConfirmCancelDevisDialogComponent {
  constructor(
    public dialogRef: MatDialogRef<ConfirmCancelDevisDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: { message: string },
  ) {}
}

