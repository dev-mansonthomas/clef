import { Component, Input, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { ApiKeysService } from '../../services/api-keys.service';
import { ApiKey } from '../../models/api-key.model';

@Component({
  selector: 'app-api-keys-manager',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './api-keys-manager.component.html',
  styleUrl: './api-keys-manager.component.scss'
})
export class ApiKeysManagerComponent implements OnInit {
  @Input() level: 'dt' | 'ul' = 'dt';
  @Input() ulId?: string;
  @Input() syncUrl: string = '';

  private readonly apiKeysService = inject(ApiKeysService);
  private readonly fb = inject(FormBuilder);

  apiKeys = signal<ApiKey[]>([]);
  loading = signal(false);
  error = signal<string | null>(null);
  newKeyForm!: FormGroup;
  showNewKeyDialog = signal(false);
  newlyCreatedKey = signal<ApiKey | null>(null);
  revealedKeys = signal<Set<string>>(new Set());

  ngOnInit(): void {
    this.initForm();
    this.loadApiKeys();
  }

  private initForm(): void {
    this.newKeyForm = this.fb.group({
      name: ['', [Validators.required, Validators.minLength(3)]]
    });
  }

  loadApiKeys(): void {
    this.loading.set(true);
    this.error.set(null);

    const request = this.level === 'dt'
      ? this.apiKeysService.listApiKeysDT()
      : this.apiKeysService.listApiKeysUL(this.ulId!);

    request.subscribe({
      next: (keys) => {
        this.apiKeys.set(keys);
        this.loading.set(false);
      },
      error: (err) => {
        console.error('Error loading API keys:', err);
        this.error.set('Erreur lors du chargement des clés API');
        this.loading.set(false);
      }
    });
  }

  onCreateKey(): void {
    if (this.newKeyForm.invalid) {
      this.newKeyForm.markAllAsTouched();
      return;
    }

    this.loading.set(true);
    this.error.set(null);

    const request = this.level === 'dt'
      ? this.apiKeysService.createApiKeyDT(this.newKeyForm.value)
      : this.apiKeysService.createApiKeyUL(this.ulId!, this.newKeyForm.value);

    request.subscribe({
      next: (key) => {
        this.newlyCreatedKey.set(key);
        this.loadApiKeys();
        this.newKeyForm.reset();
        this.showNewKeyDialog.set(false);
        this.loading.set(false);
      },
      error: (err) => {
        console.error('Error creating API key:', err);
        this.error.set('Erreur lors de la création de la clé API');
        this.loading.set(false);
      }
    });
  }

  onDeleteKey(keyId: string): void {
    if (!confirm('Êtes-vous sûr de vouloir révoquer cette clé API ?')) {
      return;
    }

    this.loading.set(true);
    this.error.set(null);

    const request = this.level === 'dt'
      ? this.apiKeysService.deleteApiKeyDT(keyId)
      : this.apiKeysService.deleteApiKeyUL(this.ulId!, keyId);

    request.subscribe({
      next: () => {
        this.loadApiKeys();
        this.loading.set(false);
      },
      error: (err) => {
        console.error('Error deleting API key:', err);
        this.error.set('Erreur lors de la suppression de la clé API');
        this.loading.set(false);
      }
    });
  }

  toggleReveal(keyId: string): void {
    const revealed = new Set(this.revealedKeys());
    if (revealed.has(keyId)) {
      revealed.delete(keyId);
    } else {
      revealed.add(keyId);
    }
    this.revealedKeys.set(revealed);
  }

  isRevealed(keyId: string): boolean {
    return this.revealedKeys().has(keyId);
  }

  copyToClipboard(text: string): void {
    navigator.clipboard.writeText(text).then(() => {
      // Could show a toast notification here
      console.log('Copied to clipboard');
    });
  }

  formatDate(dateStr: string | null): string {
    if (!dateStr) return 'Jamais';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 60) return `Il y a ${diffMins}min`;
    if (diffHours < 24) return `Il y a ${diffHours}h`;
    return `Il y a ${diffDays}j`;
  }
}

