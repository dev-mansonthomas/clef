import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AbstractControl, FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { ConfigService } from '../../services/config.service';
import { ConfigResponse } from '../../models/config.model';
import { ApiKeysManagerComponent } from '../../components/api-keys-manager/api-keys-manager.component';
import { ApiKeysService } from '../../services/api-keys.service';
import { ConfirmDialogComponent, ConfirmDialogData } from '../../shared/confirm-dialog/confirm-dialog.component';

@Component({
  selector: 'app-config-page',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, MatDialogModule, ApiKeysManagerComponent],
  templateUrl: './config-page.component.html',
  styleUrl: './config-page.component.scss'
})
export class ConfigPageComponent implements OnInit, OnDestroy {
  private readonly configService = inject(ConfigService);
  private readonly apiKeysService = inject(ApiKeysService);
  private readonly fb = inject(FormBuilder);
  private readonly dialog = inject(MatDialog);

  configForm!: FormGroup;
  loading = signal(false);
  saveSuccess = signal(false);
  saveError = signal<string | null>(null);
  emailGestionnaireDT = signal<string>('');
  syncUrl = signal<string>('');
  driveSyncStatus = signal<ConfigResponse['drive_sync_status']>('idle');
  driveSyncProcessed = signal(0);
  driveSyncTotal = signal(0);
  driveSyncMessage = signal<string | null>(null);
  driveSyncError = signal<string | null>(null);
  driveSyncCurrentVehicle = signal<string | null>(null);
  resetDriveSuccess = signal<string | null>(null);
  resetDriveLoading = signal(false);
  private driveSyncPoller: number | null = null;

  readonly driveSyncPercent = computed(() => {
    const total = this.driveSyncTotal();
    if (!total) return 0;
    return Math.min(100, Math.round((this.driveSyncProcessed() / total) * 100));
  });

  readonly driveSyncActive = computed(() => this.driveSyncStatus() === 'in_progress');

  ngOnInit(): void {
    this.initForm();
    this.loadConfig();
    this.syncUrl.set(this.apiKeysService.getSyncUrlDT());
  }

  ngOnDestroy(): void {
    this.stopDriveSyncPolling();
  }

  private initForm(): void {
    this.configForm = this.fb.group({
      drive_folder_url: ['', [this.driveFolderValidator]],
      email_destinataire_alertes: ['', [Validators.required, Validators.email]]
    });
  }

  private driveFolderValidator(control: AbstractControl) {
    const value = String(control.value ?? '').trim();
    if (!value) return null;

    const isDriveUrl = value.startsWith('https://drive.google.com/');
    const isDriveId = /^[A-Za-z0-9_-]{10,}$/.test(value);
    return isDriveUrl || isDriveId ? null : { invalidDriveFolder: true };
  }

  private loadConfig(showLoading = true): void {
    if (showLoading) {
      this.loading.set(true);
    }

    this.configService.getConfig().subscribe({
      next: (config: ConfigResponse) => {
        this.configForm.patchValue({
          drive_folder_url: config.drive_folder_url || config.drive_folder_id,
          email_destinataire_alertes: config.email_destinataire_alertes
        });
        this.emailGestionnaireDT.set(config.email_gestionnaire_dt);
        this.applyDriveSyncState(config);
        if (showLoading) {
          this.loading.set(false);
        }
      },
      error: (error) => {
        console.error('Error loading config:', error);
        this.saveError.set('Erreur lors du chargement de la configuration');
        if (showLoading) {
          this.loading.set(false);
        }
      }
    });
  }

  private applyDriveSyncState(config: ConfigResponse): void {
    this.driveSyncStatus.set(config.drive_sync_status);
    this.driveSyncProcessed.set(config.drive_sync_processed);
    this.driveSyncTotal.set(config.drive_sync_total);
    this.driveSyncMessage.set(config.drive_sync_message);
    this.driveSyncError.set(config.drive_sync_error);
    this.driveSyncCurrentVehicle.set(config.drive_sync_current_vehicle ?? null);

    if (config.drive_sync_status === 'in_progress') {
      this.startDriveSyncPolling();
      return;
    }

    if (config.drive_sync_status === 'complete') {
      this.saveSuccess.set(true);
      setTimeout(() => this.saveSuccess.set(false), 3000);
    }

    if (config.drive_sync_status === 'error' && config.drive_sync_error) {
      this.saveError.set(config.drive_sync_error);
    }

    this.stopDriveSyncPolling();
  }

  private startDriveSyncPolling(): void {
    if (this.driveSyncPoller !== null) {
      return;
    }

    this.driveSyncPoller = window.setInterval(() => {
      this.configService.getConfig().subscribe({
        next: (config) => this.applyDriveSyncState(config),
        error: (error) => {
          console.error('Error polling config status:', error);
          this.stopDriveSyncPolling();
        }
      });
    }, 1000);
  }

  private stopDriveSyncPolling(): void {
    if (this.driveSyncPoller !== null) {
      window.clearInterval(this.driveSyncPoller);
      this.driveSyncPoller = null;
    }
  }

  onSubmit(): void {
    if (this.configForm.invalid) {
      this.configForm.markAllAsTouched();
      return;
    }

    this.loading.set(true);
    this.saveSuccess.set(false);
    this.saveError.set(null);

    this.configService.updateConfig(this.configForm.value).subscribe({
      next: (config) => {
        this.applyDriveSyncState(config);
        if (config.drive_sync_status !== 'in_progress') {
          this.saveSuccess.set(true);
          setTimeout(() => this.saveSuccess.set(false), 3000);
        }
        this.loading.set(false);
      },
      error: (error) => {
        console.error('Error saving config:', error);
        this.saveError.set(error.error?.detail || 'Erreur lors de la sauvegarde');
        this.loading.set(false);
      }
    });
  }

  resetDriveSync(): void {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      width: '500px',
      data: {
        title: 'Supprimer la synchronisation Drive',
        message: `Cette action va :
        <ul>
          <li>Supprimer le lien vers le dossier Google Drive</li>
          <li>Réinitialiser l'état de progression</li>
          <li>Supprimer les liens vers les dossiers véhicules</li>
        </ul>
        <p><strong>⚠️ Les fichiers dans Google Drive ne seront PAS supprimés.</strong><br>
        Vous devrez nettoyer le contenu du dossier manuellement.</p>`,
        confirmLabel: 'Supprimer',
        cancelLabel: 'Annuler',
        confirmColor: 'warn',
        icon: 'delete_forever'
      } as ConfirmDialogData
    });

    dialogRef.afterClosed().subscribe(confirmed => {
      if (!confirmed) return;

      this.resetDriveLoading.set(true);
      this.resetDriveSuccess.set(null);
      this.saveError.set(null);

      this.configService.resetDriveSync().subscribe({
        next: (response) => {
          this.resetDriveSuccess.set(response.message);
          this.resetDriveLoading.set(false);
          // Clear the form field
          this.configForm.patchValue({ drive_folder_url: '' });
          // Reset sync state
          this.driveSyncStatus.set('idle');
          this.driveSyncProcessed.set(0);
          this.driveSyncTotal.set(0);
          this.driveSyncCurrentVehicle.set(null);
          this.driveSyncMessage.set(null);
          this.driveSyncError.set(null);
          this.stopDriveSyncPolling();
        },
        error: (error) => {
          this.saveError.set(error.error?.detail || 'Erreur lors de la suppression');
          this.resetDriveLoading.set(false);
        }
      });
    });
  }

  getFieldError(fieldName: string): string | null {
    const field = this.configForm.get(fieldName);
    if (!field || !field.touched || !field.errors) return null;

    if (field.errors['required']) return 'Ce champ est requis';
    if (field.errors['email']) return 'Email invalide';
    if (field.errors['invalidDriveFolder']) {
      return 'Renseignez une URL de dossier Google Drive ou un identifiant de dossier valide';
    }
    return null;
  }
}

