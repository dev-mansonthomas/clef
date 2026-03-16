import { Component, signal, computed, inject, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatStepper, MatStepperModule } from '@angular/material/stepper';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { Router } from '@angular/router';
import { VehicleImportService, ImportConfig, ImportResult } from '../../services/vehicle-import.service';
import { FileUploadComponent } from './components/file-upload.component';
import { ImportConfigComponent } from './components/import-config.component';
import { ColumnMapperComponent } from './components/column-mapper.component';
import { ImportResultComponent } from './components/import-result.component';

/**
 * Import Wizard Component
 * 
 * 4-step wizard for importing vehicles from CSV:
 * 1. Upload file
 * 2. Configuration (skip lines, preview)
 * 3. Column mapping
 * 4. Import result
 */
@Component({
  selector: 'app-import-wizard',
  standalone: true,
  imports: [
    CommonModule,
    MatStepperModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    FileUploadComponent,
    ImportConfigComponent,
    ColumnMapperComponent,
    ImportResultComponent
  ],
  templateUrl: './import-wizard.component.html',
  styleUrl: './import-wizard.component.scss'
})
export class ImportWizardComponent {
  private readonly router = inject(Router);
  private readonly importService = inject(VehicleImportService);
  private readonly snackBar = inject(MatSnackBar);

  @ViewChild('stepper') stepper!: MatStepper;

  // Wizard state
  uploadedFile = signal<File | null>(null);
  skipLines = signal(6);  // Default to 6 to skip header lines in CSV
  columnMapping = signal<Map<string, string>>(new Map());
  importResult = signal<ImportResult | null>(null);

  // Loading states
  uploading = signal(false);
  importing = signal(false);
  
  /**
   * Handle file selection
   */
  onFileSelected(file: File): void {
    this.uploadedFile.set(file);
  }
  
  /**
   * Handle skip lines change
   */
  onSkipLinesChange(lines: number): void {
    this.skipLines.set(lines);
  }
  
  /**
   * Handle column mapping change
   */
  onMappingChange(mapping: Map<string, string>): void {
    this.columnMapping.set(mapping);
  }

  /**
   * Cancel import and return to vehicles list
   */
  cancel(): void {
    this.router.navigate(['/vehicles']);
  }
  
  /**
   * Start import process
   */
  async startImport(): Promise<void> {
    const file = this.uploadedFile();
    if (!file) {
      this.snackBar.open('Aucun fichier sélectionné', 'Fermer', { duration: 3000 });
      return;
    }

    this.importing.set(true);
    try {
      const config: ImportConfig = {
        skip_lines: this.skipLines(),
        mappings: this.importService.convertMapping(this.columnMapping())
      };

      this.importService.importVehicles(file, config).subscribe({
        next: (result) => {
          this.importResult.set(result);
          this.stepper.next();
          this.snackBar.open(
            `Import terminé: ${result.created} créés, ${result.updated} mis à jour`,
            'Fermer',
            { duration: 5000 }
          );
        },
        error: (error) => {
          console.error('Import failed:', error);
          this.snackBar.open(
            'Erreur lors de l\'import. Veuillez réessayer.',
            'Fermer',
            { duration: 5000 }
          );
          this.importing.set(false);
        },
        complete: () => {
          this.importing.set(false);
        }
      });
    } catch (error) {
      console.error('Import failed:', error);
      this.snackBar.open(
        'Erreur lors de l\'import. Veuillez réessayer.',
        'Fermer',
        { duration: 5000 }
      );
      this.importing.set(false);
    }
  }
  
  /**
   * Finish import and return to vehicles list
   */
  finish(): void {
    this.router.navigate(['/vehicles']);
  }
}

