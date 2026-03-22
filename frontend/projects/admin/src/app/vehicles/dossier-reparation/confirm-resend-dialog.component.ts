import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatDialogModule, MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';

@Component({
  selector: 'app-confirm-resend-dialog',
  standalone: true,
  imports: [CommonModule, MatDialogModule, MatButtonModule],
  template: `
    <h2 mat-dialog-title>Renvoyer le devis pour approbation ?</h2>
    <mat-dialog-content>
      <p>{{ data.message }}</p>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button (click)="dialogRef.close(false)">Annuler</button>
      <button mat-raised-button color="primary" (click)="dialogRef.close(true)">Renvoyer</button>
    </mat-dialog-actions>
  `,
})
export class ConfirmResendDialogComponent {
  constructor(
    public dialogRef: MatDialogRef<ConfirmResendDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: { message: string },
  ) {}
}

