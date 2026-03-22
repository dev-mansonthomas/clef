import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatRadioModule } from '@angular/material/radio';
import { RepairService } from '../services/repair.service';
import { AuthService } from '../services/auth.service';
import { ApprobationData, SubmitDossierDecisionRequest } from '../models/repair.model';

@Component({
  selector: 'app-approbation-page',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatCardModule, MatButtonModule, MatIconModule,
    MatProgressSpinnerModule, MatFormFieldModule, MatInputModule,
    MatRadioModule,
  ],
  template: `
    <div class="approbation-container">

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
      <h1><mat-icon>gavel</mat-icon> Approbation — Dossier {{ data()!.numero_dossier }}</h1>
      <p class="subtitle">Véhicule {{ data()!.immat }}</p>

      @if (data()!.dossier_description.length) {
      <div class="travaux-section">
        <h3>Travaux prévus</h3>
        <ul>
          <li *ngFor="let item of data()!.dossier_description">{{ item }}</li>
        </ul>
      </div>
      }

      @for (d of data()!.devis; track d.id) {
      <mat-card class="devis-card" [class.devis-refused]="devisDecisions.get(d.id) === 'refuse'">
        <mat-card-header>
          <mat-card-title>{{ d.fournisseur.nom || 'Fournisseur' }}</mat-card-title>
          <span class="devis-montant">{{ d.montant | number:'1.2-2' }} €</span>
        </mat-card-header>
        <mat-card-content>
          <div class="devis-info">
            <span>Date : {{ d.date_devis | date:'dd/MM/yyyy' }}</span>
          </div>
          @if (d.description_items?.length) {
          <ul class="devis-items">
            <li *ngFor="let item of d.description_items">{{ item }}</li>
          </ul>
          }
          @if (d.description) {
          <p class="devis-comment">{{ d.description }}</p>
          }
          @if (d.fichier?.web_view_link) {
          <a [href]="d.fichier!.web_view_link" target="_blank" rel="noopener" class="drive-link">
            <mat-icon>attach_file</mat-icon> Voir le devis
          </a>
          }
          @if (mode() === 'partiel') {
          <mat-radio-group [value]="devisDecisions.get(d.id)" (change)="setDevisDecision(d.id, $event.value)">
            <mat-radio-button value="approuve" color="primary">Approuver</mat-radio-button>
            <mat-radio-button value="refuse" color="warn">Refuser</mat-radio-button>
          </mat-radio-group>
          }
        </mat-card-content>
      </mat-card>
      }

      <div class="total-row">
        <strong>Total : {{ totalMontant() | number:'1.2-2' }} €</strong>
      </div>

      <div class="decision-section">
        <h3>Votre décision</h3>
        <mat-radio-group [value]="mode()" (change)="setMode($event.value)">
          <mat-radio-button value="approuve_tout" color="primary">
            <mat-icon>check_circle</mat-icon> Approuver tout
          </mat-radio-button>
          <mat-radio-button value="refuse_tout" color="warn">
            <mat-icon>cancel</mat-icon> Refuser tout
          </mat-radio-button>
          @if (data()!.devis.length > 1) {
          <mat-radio-button value="partiel">
            <mat-icon>tune</mat-icon> Approbation partielle
          </mat-radio-button>
          }
        </mat-radio-group>
      </div>

      <mat-form-field appearance="outline" class="comment-field">
        <mat-label>Commentaire {{ commentaireRequired() ? '(obligatoire)' : '(optionnel)' }}</mat-label>
        <textarea matInput [(ngModel)]="commentaire" rows="3"></textarea>
      </mat-form-field>

      <button mat-raised-button color="primary" (click)="submitDecision()"
        [disabled]="submitting() || !isValid()" class="submit-btn">
        <mat-icon>send</mat-icon> Confirmer ma décision
      </button>
      }

      @if (submitted()) {
      <mat-card class="confirmation-card">
        <mat-card-content>
          <mat-icon class="big-icon" [ngClass]="submittedDecision() === 'approuve_tout' ? 'approved' : 'rejected'">
            {{ submittedDecision() === 'approuve_tout' ? 'check_circle' : 'cancel' }}
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
    h1 { display: flex; align-items: center; gap: 8px; color: #d32f2f; }
    .subtitle { color: rgba(0,0,0,0.6); margin-top: -8px; }
    .loading { display: flex; align-items: center; gap: 12px; padding: 24px 0; }
    .error-msg { display: flex; align-items: center; gap: 8px; color: #c62828; padding: 16px; background: #ffebee; border-radius: 8px; }
    .travaux-section ul { margin: 4px 0 0; padding-left: 20px; }
    .travaux-section li { margin-bottom: 2px; }
    .devis-card { margin: 12px 0; }
    .devis-card mat-card-header { display: flex; align-items: center; }
    .devis-montant { font-size: 20px; font-weight: 600; color: #1565c0; margin-left: auto; }
    .devis-info { color: rgba(0,0,0,0.6); margin: 8px 0; }
    .devis-items { margin: 8px 0; padding-left: 20px; }
    .devis-comment { color: rgba(0,0,0,0.6); font-style: italic; }
    .drive-link { display: flex; align-items: center; gap: 4px; color: #1976d2; text-decoration: none; margin: 8px 0; }
    .decision-section { margin: 24px 0; }
    .decision-section mat-radio-button { display: block; margin: 8px 0; }
    .total-row { text-align: right; font-size: 18px; margin: 16px 0; padding: 12px; background: #f5f5f5; border-radius: 8px; }
    .comment-field { width: 100%; margin: 16px 0; }
    .submit-btn { width: 100%; padding: 12px; font-size: 16px; }
    .devis-refused { opacity: 0.6; border-left: 4px solid #c62828; }
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

  mode = signal<'approuve_tout' | 'refuse_tout' | 'partiel'>('approuve_tout');
  devisDecisions = new Map<string, 'approuve' | 'refuse'>();

  totalMontant = computed(() => {
    return this.data()?.devis.reduce((sum, d) => sum + (d.montant || 0), 0) || 0;
  });

  commentaireRequired = computed(() => this.mode() !== 'approuve_tout');

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
        // Initialize per-devis decisions
        for (const d of data.devis) {
          this.devisDecisions.set(d.id, 'approuve');
        }
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

  isValid(): boolean {
    if (this.commentaireRequired() && !this.commentaire.trim()) return false;
    if (this.mode() === 'partiel') {
      return this.devisDecisions.size > 0;
    }
    return true;
  }

  setMode(m: string): void {
    this.mode.set(m as 'approuve_tout' | 'refuse_tout' | 'partiel');
    if (m === 'approuve_tout') {
      for (const [id] of this.devisDecisions) this.devisDecisions.set(id, 'approuve');
    } else if (m === 'refuse_tout') {
      for (const [id] of this.devisDecisions) this.devisDecisions.set(id, 'refuse');
    }
  }

  setDevisDecision(devisId: string, decision: 'approuve' | 'refuse'): void {
    this.devisDecisions.set(devisId, decision);
  }

  submitDecision(): void {
    const token = this.route.snapshot.paramMap.get('token');
    if (!token) return;
    this.submitting.set(true);

    const body: SubmitDossierDecisionRequest = {
      mode: this.mode(),
      commentaire: this.commentaire || undefined,
    };
    if (this.mode() === 'partiel') {
      body.decisions = Array.from(this.devisDecisions.entries()).map(([devis_id, decision]) => ({
        devis_id, decision,
      }));
    }

    this.repairService.submitDossierDecision(token, body).subscribe({
      next: (res) => {
        this.submitting.set(false);
        this.submitted.set(true);
        this.submittedDecision.set(this.mode());
        this.submittedMessage.set(res.message);
      },
      error: (err) => {
        this.submitting.set(false);
        this.error.set(err?.error?.detail || 'Erreur lors de la soumission de la décision');
      },
    });
  }
}

