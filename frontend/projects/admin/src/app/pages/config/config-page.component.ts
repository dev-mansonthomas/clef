import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { ConfigService } from '../../services/config.service';
import { ConfigResponse } from '../../models/config.model';
import { ApiKeysManagerComponent } from '../../components/api-keys-manager/api-keys-manager.component';
import { ApiKeysService } from '../../services/api-keys.service';

@Component({
  selector: 'app-config-page',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, ApiKeysManagerComponent],
  templateUrl: './config-page.component.html',
  styleUrl: './config-page.component.scss'
})
export class ConfigPageComponent implements OnInit {
  private readonly configService = inject(ConfigService);
  private readonly apiKeysService = inject(ApiKeysService);
  private readonly fb = inject(FormBuilder);

  configForm!: FormGroup;
  loading = signal(false);
  saveSuccess = signal(false);
  saveError = signal<string | null>(null);
  emailGestionnaireDT = signal<string>('');
  syncUrl = signal<string>('');

  ngOnInit(): void {
    this.initForm();
    this.loadConfig();
    this.syncUrl.set(this.apiKeysService.getSyncUrlDT());
  }

  private initForm(): void {
    this.configForm = this.fb.group({
      sheets_url_vehicules: ['', [Validators.required, this.googleUrlValidator]],
      sheets_url_benevoles: ['', [Validators.required, this.googleUrlValidator]],
      sheets_url_responsables: ['', [Validators.required, this.googleUrlValidator]],
      template_doc_url: ['', [Validators.required, this.googleUrlValidator]],
      email_destinataire_alertes: ['', [Validators.required, Validators.email]]
    });
  }

  private googleUrlValidator(control: any) {
    const value = control.value;
    if (!value) return null;
    if (!value.startsWith('https://docs.google.com/')) {
      return { invalidGoogleUrl: true };
    }
    return null;
  }

  private loadConfig(): void {
    this.loading.set(true);
    this.configService.getConfig().subscribe({
      next: (config: ConfigResponse) => {
        this.configForm.patchValue({
          sheets_url_vehicules: config.sheets_url_vehicules,
          sheets_url_benevoles: config.sheets_url_benevoles,
          sheets_url_responsables: config.sheets_url_responsables,
          template_doc_url: config.template_doc_url,
          email_destinataire_alertes: config.email_destinataire_alertes
        });
        this.emailGestionnaireDT.set(config.email_gestionnaire_dt);
        this.loading.set(false);
      },
      error: (error) => {
        console.error('Error loading config:', error);
        this.saveError.set('Erreur lors du chargement de la configuration');
        this.loading.set(false);
      }
    });
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
      next: () => {
        this.saveSuccess.set(true);
        this.loading.set(false);
        setTimeout(() => this.saveSuccess.set(false), 3000);
      },
      error: (error) => {
        console.error('Error saving config:', error);
        this.saveError.set(error.error?.detail || 'Erreur lors de la sauvegarde');
        this.loading.set(false);
      }
    });
  }

  getFieldError(fieldName: string): string | null {
    const field = this.configForm.get(fieldName);
    if (!field || !field.touched || !field.errors) return null;

    if (field.errors['required']) return 'Ce champ est requis';
    if (field.errors['email']) return 'Email invalide';
    if (field.errors['invalidGoogleUrl']) return 'L\'URL doit être une URL Google Docs/Sheets';
    return null;
  }
}

