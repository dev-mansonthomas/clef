import { Component, inject, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { UniteLocale } from '../../../models/unite-locale.model';

export interface ULDialogData {
  ul?: UniteLocale;
  mode: 'create' | 'edit';
}

@Component({
  selector: 'app-ul-dialog',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule
  ],
  template: `
    <h2 mat-dialog-title>{{ data.mode === 'create' ? 'Ajouter une UL' : 'Modifier l\'UL' }}</h2>
    <mat-dialog-content>
      <form [formGroup]="ulForm">
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>ID de l'UL</mat-label>
          <input matInput formControlName="id" [readonly]="data.mode === 'edit'">
          <mat-hint>Exemple: 81, 82, etc.</mat-hint>
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Nom de l'UL</mat-label>
          <input matInput formControlName="nom">
          <mat-hint>Exemple: UL 01-02, UL Paris 15, etc.</mat-hint>
        </mat-form-field>
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button (click)="onCancel()">Annuler</button>
      <button mat-raised-button color="primary" (click)="onSave()" [disabled]="!ulForm.valid">
        {{ data.mode === 'create' ? 'Créer' : 'Enregistrer' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    .full-width {
      width: 100%;
      margin-bottom: 16px;
    }

    mat-dialog-content {
      min-width: 400px;
      padding: 20px 24px;
    }
  `]
})
export class ULDialogComponent {
  private readonly fb = inject(FormBuilder);
  private readonly dialogRef = inject(MatDialogRef<ULDialogComponent>);
  
  ulForm: FormGroup;

  constructor(@Inject(MAT_DIALOG_DATA) public data: ULDialogData) {
    this.ulForm = this.fb.group({
      id: [
        { value: data.ul?.id || '', disabled: data.mode === 'edit' },
        [Validators.required, Validators.pattern(/^[0-9]+$/)]
      ],
      nom: [data.ul?.nom || '', Validators.required]
    });
  }

  onCancel(): void {
    this.dialogRef.close();
  }

  onSave(): void {
    if (this.ulForm.valid) {
      const formValue = this.ulForm.getRawValue();
      this.dialogRef.close(formValue);
    }
  }
}

