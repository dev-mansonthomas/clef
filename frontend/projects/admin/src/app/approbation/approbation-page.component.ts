import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { RepairService } from '../services/repair.service';
import { AuthService } from '../services/auth.service';
import { ApprobationData } from '../models/repair.model';

@Component({
  selector: 'app-approbation-page',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatCardModule, MatButtonModule, MatIconModule,
    MatProgressSpinnerModule, MatFormFieldModule, MatInputModule,
  ],
  template: `
    <div class="approbation-container">
      <div class="approbation-header">
        <h1><mat-icon>gavel</mat-icon> Approbation de devis — CLEF</h1>
      </div>

      @if (loading()) {
      <div class="loading">
        <mat-spinner diameter="40"></mat-spinner>
        <span>Chargement…</span>
      </div>
      }

      @if (error()) {
      <div class="error-msg">
        <mat-icon>error</mat-icon>
        <p>{{ error() }}</p>
      </div>
      }

      @if (unauthorized()) {
      <div class="error-msg">
        <mat-icon>block</mat-icon>
        <p>Vous n'êtes pas autorisé à voir cette approbation. Seul le valideur désigné peut approuver ce devis.</p>
      </div>
      }

      @if (data() && !loading() && !submitted() && !unauthorized()) {
      <mat-card>
        <mat-card-header>
          <mat-card-title>Devis — {{ data()!.devis.fournisseur?.nom || 'Fournisseur' }}</mat-card-title>
          <mat-card-subtitle>Dossier {{ data()!.numero_dossier }} · {{ data()!.immat }}</mat-card-subtitle>
        </mat-card-header>
        <mat-card-content>
          <div class="info-grid">
            <div class="info-item"><strong>Dossier</strong>
              <ul class="dossier-desc-list" *ngIf="data()!.dossier_description?.length">
                <li *ngFor="let item of data()!.dossier_description">{{ item }}</li>
              </ul>
            </div>
            <div class="info-item"><strong>Fournisseur</strong><span>{{ data()!.devis.fournisseur?.nom }}</span></div>
            <div class="info-item"><strong>Description</strong><span>{{ data()!.devis.description }}</span></div>
            <div class="info-item highlight"><strong>Montant</strong><span>{{ data()!.devis.montant | number:'1.2-2' }} €</span></div>
            <div class="info-item"><strong>Date du devis</strong><span>{{ data()!.devis.date_devis | date:'dd/MM/yyyy' }}</span></div>
          </div>

          @if (data()!.devis.fichier?.web_view_link) {
          <div class="drive-link">
            <a [href]="data()!.devis.fichier!.web_view_link" target="_blank" rel="noopener">
              <mat-icon>attach_file</mat-icon> Voir le devis sur Google Drive
            </a>
          </div>
          }

          @if (data()!.status !== 'pending') {
          <div class="already-decided">
            <mat-icon>info</mat-icon>
            Ce devis a déjà été {{ data()!.status === 'approuve' ? 'approuvé' : 'refusé' }}.
            Vous pouvez modifier votre décision.
          </div>
          }

          <mat-form-field appearance="outline" class="comment-field">
            <mat-label>Commentaire (optionnel)</mat-label>
            <textarea matInput [(ngModel)]="commentaire" rows="3"></textarea>
          </mat-form-field>

          <div class="decision-buttons">
            <button mat-raised-button class="approve-btn" (click)="submitDecision('approuve')" [disabled]="submitting()">
              <mat-icon>check_circle</mat-icon> Approuver
            </button>
            <button mat-raised-button class="reject-btn" (click)="submitDecision('refuse')" [disabled]="submitting()">
              <mat-icon>cancel</mat-icon> Refuser
            </button>
          </div>
        </mat-card-content>
      </mat-card>
      }

      @if (submitted()) {
      <mat-card class="confirmation-card">
        <mat-card-content>
          <mat-icon class="big-icon" [ngClass]="submittedDecision() === 'approuve' ? 'approved' : 'rejected'">
            {{ submittedDecision() === 'approuve' ? 'check_circle' : 'cancel' }}
          </mat-icon>
          <h2>{{ submittedMessage() }}</h2>
          <p>Vous pouvez fermer cette page.</p>
        </mat-card-content>
      </mat-card>
      }
    </div>
  `,
  styles: [`
    .approbation-container { max-width: 640px; margin: 24px auto; padding: 0 16px; }
    .approbation-header h1 { display: flex; align-items: center; gap: 8px; color: #d32f2f; }
    .loading { display: flex; align-items: center; gap: 12px; padding: 24px 0; }
    .error-msg { display: flex; align-items: center; gap: 8px; color: #c62828; padding: 16px; background: #ffebee; border-radius: 8px; }
    .info-grid { display: grid; gap: 12px; margin: 16px 0; }
    .info-item { display: flex; flex-direction: column; gap: 2px; }
    .info-item strong { font-size: 12px; color: rgba(0,0,0,0.54); text-transform: uppercase; }
    .dossier-desc-list { margin: 4px 0 0; padding-left: 20px; }
    .dossier-desc-list li { margin-bottom: 2px; }
    .info-item.highlight span { font-size: 20px; font-weight: 600; color: #1565c0; }
    .drive-link { margin: 16px 0; padding: 12px 16px; background: #e3f2fd; border-radius: 8px; border-left: 4px solid #1976d2; }
    .drive-link a { display: flex; align-items: center; gap: 8px; color: #1976d2; text-decoration: none; font-weight: 500; }
    .already-decided { display: flex; align-items: center; gap: 8px; padding: 12px; background: #fff9c4; border-radius: 8px; margin: 12px 0; }
    .comment-field { width: 100%; margin: 16px 0; }
    .decision-buttons { display: flex; gap: 16px; margin-top: 16px; }
    .approve-btn { background: #2e7d32 !important; color: white !important; }
    .reject-btn { background: #c62828 !important; color: white !important; }
    .confirmation-card { text-align: center; padding: 32px; }
    .big-icon { font-size: 64px; width: 64px; height: 64px; }
    .big-icon.approved { color: #2e7d32; }
    .big-icon.rejected { color: #c62828; }
  `],
})
export class ApprobationPageComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly repairService = inject(RepairService);
  private readonly authService = inject(AuthService);

  data = signal<ApprobationData | null>(null);
  loading = signal(true);
  error = signal<string | null>(null);
  unauthorized = signal(false);
  commentaire = '';
  submitting = signal(false);
  submitted = signal(false);
  submittedDecision = signal('');
  submittedMessage = signal('');

  ngOnInit(): void {
    const token = this.route.snapshot.paramMap.get('token');
    if (!token) {
      this.error.set('Token manquant');
      this.loading.set(false);
      return;
    }
    this.repairService.getApprobationData(token).subscribe({
      next: (data) => {
        this.data.set(data);
        this.loading.set(false);
        // Verify the logged-in user is the designated validator
        const currentEmail = this.authService.currentUserValue?.email?.toLowerCase();
        const valideurEmail = data.valideur_email?.toLowerCase();
        if (currentEmail && valideurEmail && currentEmail !== valideurEmail && currentEmail !== 'thomas.manson@croix-rouge.fr') {
          this.unauthorized.set(true);
        }
      },
      error: () => { this.error.set('Token invalide ou expiré'); this.loading.set(false); },
    });
  }

  submitDecision(decision: 'approuve' | 'refuse'): void {
    const token = this.route.snapshot.paramMap.get('token');
    if (!token) return;
    this.submitting.set(true);
    this.repairService.submitDecision(token, { decision, commentaire: this.commentaire || undefined }).subscribe({
      next: (res) => {
        this.submitting.set(false);
        this.submitted.set(true);
        this.submittedDecision.set(decision);
        this.submittedMessage.set(res.message);
      },
      error: (err) => {
        this.submitting.set(false);
        this.error.set(err?.error?.detail || 'Erreur lors de la soumission de la décision');
      },
    });
  }
}

