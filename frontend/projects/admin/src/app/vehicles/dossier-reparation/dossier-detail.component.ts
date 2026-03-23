import { Component, Input, Output, EventEmitter, OnInit, OnChanges, SimpleChanges, inject, ChangeDetectorRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule, FormControl } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatDividerModule } from '@angular/material/divider';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatAutocompleteModule, MatAutocompleteTrigger } from '@angular/material/autocomplete';
import { Observable, startWith, map } from 'rxjs';
import { RepairService } from '../../services/repair.service';
import { ValideurService } from '../../services/valideur.service';
import { ContactCCService } from '../../services/contact-cc.service';
import { DossierReparation, Devis, Facture, FactureCreateResponse, AuditEntry, Valideur, ContactCC } from '../../models/repair.model';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { DevisFormComponent } from './devis-form.component';
import { FactureFormComponent } from './facture-form.component';
import { ConfirmResendDialogComponent } from './confirm-resend-dialog.component';
import { ConfirmCancelDevisDialogComponent } from './confirm-cancel-devis-dialog.component';

@Component({
  selector: 'app-dossier-detail',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatChipsModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatDividerModule,
    MatFormFieldModule,
    MatInputModule,
    MatDialogModule,
    MatAutocompleteModule,
    MatCheckboxModule,
    DevisFormComponent,
    FactureFormComponent,
  ],
  template: `
    <div class="dossier-detail" *ngIf="!loading && dossier">
      <div class="detail-header">
        <button mat-button type="button" (click)="back.emit()"><mat-icon>arrow_back</mat-icon> Retour à la liste</button>
      </div>

      <mat-card>
        <mat-card-header class="dossier-header-row">
          <mat-card-title class="dossier-header-inline">
            <span>{{ dossier.numero }}</span>
            <ng-container *ngIf="dossier.titre">
              <span class="header-separator">·</span>
              <span class="header-titre">{{ dossier.titre }}</span>
            </ng-container>
            <span class="header-separator">·</span>
            <span class="header-date">Créé le {{ dossier.cree_le | date:'dd/MM/yyyy HH:mm' }}</span>
            <span class="header-separator">·</span>
            <span class="statut-badge" [ngClass]="'statut-' + dossier.statut">{{ statutLabel(dossier.statut) }}</span>
          </mat-card-title>
        </mat-card-header>
        <mat-card-content>

          <h4>Description</h4>
          <ul class="description-list" *ngIf="dossier.description.length">
            <li *ngFor="let item of dossier.description">{{ item }}</li>
          </ul>
          <p class="empty-section" *ngIf="!dossier.description.length">Aucune description.</p>
          <div *ngIf="dossier.commentaire" class="commentaire-block">
            <strong>Commentaire :</strong> {{ dossier.commentaire }}
          </div>

          <mat-divider></mat-divider>

          <div class="action-buttons">
            <button mat-raised-button type="button" (click)="showDevisForm = true" [disabled]="dossier.statut !== 'ouvert' || showDevisForm">
              <mat-icon>request_quote</mat-icon> Enregistrer un devis
            </button>
            <button mat-raised-button type="button" (click)="showFactureForm = true" [disabled]="dossier.statut !== 'ouvert' || showFactureForm">
              <mat-icon>receipt</mat-icon> Enregistrer une facture
            </button>
            <button mat-stroked-button type="button" *ngIf="dossier.statut === 'ouvert'" (click)="updateStatut('cloture')" [disabled]="actionLoading">
              <mat-icon>lock</mat-icon> Clôturer le dossier
            </button>
            <button mat-stroked-button type="button" *ngIf="dossier.statut === 'cloture'" (click)="updateStatut('ouvert')" [disabled]="actionLoading">
              <mat-icon>lock_open</mat-icon> Réouvrir le dossier
            </button>
            <button mat-stroked-button type="button" color="warn" *ngIf="dossier.statut === 'ouvert'" (click)="updateStatut('annule')" [disabled]="actionLoading">
              <mat-icon>cancel</mat-icon> Annuler le dossier
            </button>
            <button mat-raised-button color="primary" type="button"
              *ngIf="dossier.statut === 'ouvert' && hasPendingDevis()"
              (click)="openBulkApprovalForm()" [disabled]="approvalLoading || bulkApprovalMode">
              <mat-icon>playlist_add_check</mat-icon> Envoyer tout pour approbation
            </button>
          </div>
          <!-- Bulk approval form -->
          <div class="approval-form" *ngIf="bulkApprovalMode">
            <mat-form-field appearance="outline" class="approval-email-field">
              <mat-label>Valideur</mat-label>
              <input matInput [formControl]="valideurSearchControl" [matAutocomplete]="valideurAuto"
                     placeholder="Rechercher un valideur…" (focus)="onValideurFocus()">
              <button mat-icon-button matSuffix type="button" (click)="toggleValideurPanel($event)" tabindex="-1">
                <mat-icon>arrow_drop_down</mat-icon>
              </button>
              <mat-autocomplete #valideurAuto="matAutocomplete" [displayWith]="displayValideurFn" (optionSelected)="onValideurSelected($event.option.value)">
                <mat-option *ngFor="let v of filteredValideurs$ | async" [value]="v">
                  {{ v.prenom }} {{ v.nom }} <span class="valideur-hint"> — {{ v.email }}</span>
                </mat-option>
              </mat-autocomplete>
            </mat-form-field>
            <div class="cc-checkboxes" *ngIf="contactsCC.length > 0">
              <span class="cc-label">CC :</span>
              <mat-checkbox *ngFor="let cc of contactsCC" [checked]="isCCSelected(cc.email)" (change)="toggleCC(cc.email)">
                {{ cc.prenom }} {{ cc.nom }}
              </mat-checkbox>
            </div>
            <button mat-raised-button color="primary" type="button" (click)="sendBulkApproval()" [disabled]="approvalLoading || !approvalEmail">
              <mat-icon>send</mat-icon> Envoyer tout
            </button>
            <button mat-button type="button" (click)="bulkApprovalMode = false">Annuler</button>
          </div>

          <mat-divider></mat-divider>

          <h4>Devis</h4>
          <app-devis-form *ngIf="showDevisForm" [dt]="dt" [immat]="immat" [numero]="numero"
            [dossierDescription]="dossier.description || []" [dossierTitre]="dossier.titre || ''"
            (devisCreated)="onDevisCreated($event)" (cancelled)="showDevisForm = false"></app-devis-form>
          <p class="empty-section" *ngIf="!dossier.devis.length && !showDevisForm">Aucun devis enregistré.</p>
          <table class="devis-table" *ngIf="dossier.devis.length">
            <thead>
              <tr>
                <th class="col-numero">N°</th>
                <th>Date</th>
                <th>Fournisseur</th>
                <th class="col-right">Montant</th>
                <th>Statut</th>
                <th>Fichier</th>
                <th class="col-actions">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let d of dossier.devis" [class.devis-annule-row]="d.statut === 'annule'">
                <td class="col-numero">Devis {{ padId(d.id) }}</td>
                <td>{{ d.date_devis | date:'dd/MM/yyyy' }}</td>
                <td>{{ d.fournisseur.nom || d.id }}</td>
                <td class="col-right">{{ d.montant | number:'1.2-2' }} €</td>
                <td><span class="devis-statut-badge" [ngClass]="'devis-statut-' + d.statut">{{ devisStatutLabel(d.statut) }}</span></td>
                <td>
                  <a *ngIf="d.fichier" [href]="d.fichier.web_view_link" target="_blank" rel="noopener" class="fichier-link">📎 {{ d.fichier.name }}</a>
                </td>
                <td class="col-actions">
                  <div class="action-cell">
                    <button type="button" mat-icon-button *ngIf="(d.statut === 'en_attente' || d.statut === 'refuse') && dossier.statut === 'ouvert'"
                      (click)="startEditDevis(d)" [disabled]="!!editingDevis" title="Modifier">
                      <mat-icon>edit</mat-icon>
                    </button>
                    <button type="button" mat-stroked-button *ngIf="d.statut === 'en_attente' && dossier.statut === 'ouvert'"
                      (click)="openApprovalForm(d)" [disabled]="approvalLoading" class="approval-btn">
                      <mat-icon>send</mat-icon> Envoyer pour approbation
                    </button>
                    <button type="button" mat-stroked-button *ngIf="(d.statut === 'envoye' || d.statut === 'refuse') && dossier.statut === 'ouvert'"
                      (click)="confirmResend(d)" [disabled]="approvalLoading" class="approval-btn">
                      <mat-icon>replay</mat-icon> Renvoyer pour approbation
                    </button>
                    <button type="button" mat-stroked-button *ngIf="d.statut === 'approuve' && dossier.statut === 'ouvert' && !getFactureForDevis(d.id)"
                      (click)="createFactureForDevis(d)" class="add-facture-btn">
                      <mat-icon>receipt</mat-icon> Ajouter facture
                    </button>
                    <button type="button" mat-stroked-button *ngIf="getFactureForDevis(d.id)"
                      (click)="viewFactureForDevis(d)" class="add-facture-btn">
                      <mat-icon>visibility</mat-icon> Voir Facture
                    </button>
                    <!-- Cancel button — ALWAYS far right, RED -->
                    <button type="button" mat-icon-button *ngIf="d.statut !== 'annule' && dossier.statut === 'ouvert'"
                      (click)="annulerDevis(d)" [disabled]="actionLoading"
                      title="Annuler le devis" class="cancel-devis-btn">
                      <mat-icon>cancel</mat-icon>
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <!-- Inline approval form -->
          <div class="approval-form" *ngIf="approvalDevis">
            <mat-form-field appearance="outline" class="approval-email-field">
              <mat-label>Valideur</mat-label>
              <input matInput [formControl]="valideurSearchControl" [matAutocomplete]="valideurAuto"
                     placeholder="Rechercher un valideur…" (focus)="onValideurFocus()">
              <button mat-icon-button matSuffix type="button" (click)="toggleValideurPanel($event)" tabindex="-1">
                <mat-icon>arrow_drop_down</mat-icon>
              </button>
              <mat-autocomplete #valideurAuto="matAutocomplete" [displayWith]="displayValideurFn" (optionSelected)="onValideurSelected($event.option.value)">
                <mat-option *ngFor="let v of filteredValideurs$ | async" [value]="v">
                  {{ v.prenom }} {{ v.nom }} <span class="valideur-hint"> — {{ v.email }}</span>
                </mat-option>
              </mat-autocomplete>
            </mat-form-field>
            <div class="cc-checkboxes" *ngIf="contactsCC.length > 0">
              <span class="cc-label">CC :</span>
              <mat-checkbox *ngFor="let cc of contactsCC" [checked]="isCCSelected(cc.email)" (change)="toggleCC(cc.email)">
                {{ cc.prenom }} {{ cc.nom }}
              </mat-checkbox>
            </div>
            <button mat-raised-button color="primary" type="button" (click)="sendForApproval()" [disabled]="approvalLoading || !approvalEmail">
              <mat-icon>send</mat-icon> Envoyer
            </button>
            <button mat-button type="button" (click)="approvalDevis = null">Annuler</button>
          </div>
          <!-- Inline edit form -->
          <app-devis-form *ngIf="editingDevis" [dt]="dt" [immat]="immat" [numero]="numero"
            [dossierDescription]="dossier.description || []" [dossierTitre]="dossier.titre || ''"
            [editDevis]="editingDevis"
            (devisUpdated)="onDevisUpdated($event)" (cancelled)="editingDevis = null"></app-devis-form>

          <h4>Factures</h4>
          <app-facture-form *ngIf="showFactureForm" [dt]="dt" [immat]="immat" [numero]="numero"
            [devisList]="dossier.devis || []"
            [preselectedDevisId]="preselectedDevisId"
            [devisLabel]="factureDevisLabel"
            [editFacture]="editingFacture"
            [inheritedDescriptionItems]="getDevisDescriptionItems()"
            [inheritedDescriptionTravaux]="getDevisDescriptionTravaux()"
            (factureCreated)="onFactureCreated($event)" (cancelled)="onFactureCancelled()"></app-facture-form>

          <!-- Read-only facture detail view -->
          <div class="facture-detail-view" *ngIf="viewingFacture">
            <mat-card>
              <mat-card-header>
                <mat-card-title>Facture — {{ viewingFacture.fournisseur.nom }}</mat-card-title>
              </mat-card-header>
              <mat-card-content>
                <p><strong>Date :</strong> {{ viewingFacture.date_facture | date:'dd/MM/yyyy' }}</p>
                <p><strong>Classification :</strong> {{ classificationLabel(viewingFacture.classification) }}</p>
                <p *ngIf="viewingFacture.description"><strong>Description :</strong> {{ viewingFacture.description }}</p>
                <p><strong>Montant total :</strong> {{ viewingFacture.montant_total | number:'1.2-2' }} €</p>
                <p><strong>Montant CRF :</strong> {{ viewingFacture.montant_crf | number:'1.2-2' }} €</p>
                <p *ngIf="viewingFacture.fichier"><strong>Fichier :</strong> <a [href]="viewingFacture.fichier.web_view_link" target="_blank" rel="noopener" class="fichier-link">📎 {{ viewingFacture.fichier.name }}</a></p>
                <div class="form-actions" style="margin-top:12px;">
                  <button mat-button type="button" (click)="viewingFacture = null">Fermer</button>
                  <button mat-raised-button color="primary" type="button" (click)="startEditFacture(viewingFacture)" *ngIf="dossier.statut === 'ouvert'">
                    <mat-icon>edit</mat-icon> Modifier
                  </button>
                </div>
              </mat-card-content>
            </mat-card>
          </div>
          <p class="empty-section" *ngIf="!dossier.factures.length && !showFactureForm">Aucune facture enregistrée.</p>
          <table class="factures-table" *ngIf="dossier.factures.length">
            <thead>
              <tr>
                <th>Date</th>
                <th>Fournisseur</th>
                <th>Classification</th>
                <th class="col-right">Total</th>
                <th class="col-right">CRF</th>
                <th>Fichier</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let f of dossier.factures">
                <td>{{ f.date_facture | date:'dd/MM/yyyy' }}</td>
                <td>{{ f.fournisseur.nom || f.id }}</td>
                <td class="item-classification">{{ classificationLabel(f.classification) }}</td>
                <td class="col-right">{{ f.montant_total | number:'1.2-2' }} €</td>
                <td class="col-right item-montant-crf">CRF: {{ f.montant_crf | number:'1.2-2' }} €</td>
                <td><a *ngIf="f.fichier" [href]="f.fichier.web_view_link" target="_blank" rel="noopener" class="fichier-link">📎 {{ f.fichier.name }}</a></td>
              </tr>
            </tbody>
          </table>
          <mat-divider></mat-divider>

          <h4>Historique</h4>
          <div class="timeline" *ngIf="historique.length">
            <div class="timeline-entry" *ngFor="let entry of historique">
              <mat-icon [ngClass]="'timeline-icon timeline-icon-' + entry.action"
                >{{ actionIcon(entry.action) }}</mat-icon>
              <div class="timeline-content">
                <span class="timeline-date">{{ entry.date | date:'dd/MM/yyyy HH:mm' }}</span>
                <span class="timeline-details">{{ entry.details }}</span>
                <span class="timeline-auteur">par {{ entry.auteur }}</span>
              </div>
            </div>
          </div>
          <p class="empty-section" *ngIf="!historique.length && !historiqueLoading">Aucun historique.</p>
          <mat-spinner diameter="20" *ngIf="historiqueLoading"></mat-spinner>
        </mat-card-content>
      </mat-card>
    </div>

    <div *ngIf="loading" class="loading-container">
      <mat-spinner diameter="32"></mat-spinner>
      <span>Chargement du dossier…</span>
    </div>
  `,
  styles: [`
    .detail-header { margin-bottom: 12px; }
    .dossier-header-row { margin-bottom: 8px; }
    .dossier-header-inline { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .header-separator { color: rgba(0,0,0,0.38); }
    .header-date { font-size: 14px; font-weight: 400; color: rgba(0,0,0,0.54); }
    .header-titre { font-size: 16px; font-weight: 400; }
    .statut-badge { display: inline-block; padding: 4px 12px; border-radius: 16px; font-size: 12px; font-weight: 500; text-transform: uppercase; }
    .statut-ouvert { background: #e8f5e9; color: #2e7d32; }
    .statut-cloture { background: #eeeeee; color: #616161; }
    .statut-annule { background: #ffebee; color: #c62828; }
    .description-list { margin: 8px 0 16px; padding-left: 20px; }
    .description-list li { margin-bottom: 4px; }
    .commentaire-block { margin: 8px 0 16px; padding: 8px 12px; background: #f5f5f5; border-radius: 4px; font-style: italic; }
    .action-buttons { display: flex; gap: 12px; margin: 16px 0; flex-wrap: wrap; }
    .empty-section { color: rgba(0,0,0,0.54); font-style: italic; }
    .loading-container { display: flex; align-items: center; gap: 12px; padding: 24px 0; }
    h4 { margin: 16px 0 8px; font-weight: 500; }
    .devis-table, .factures-table { width: 100%; border-collapse: collapse; margin: 8px 0 16px; }
    .devis-table th, .devis-table td, .factures-table th, .factures-table td { padding: 8px 12px; text-align: left; border-bottom: 1px solid rgba(0,0,0,0.08); vertical-align: middle; }
    .devis-table th, .factures-table th { font-weight: 500; font-size: 12px; color: rgba(0,0,0,0.54); text-transform: uppercase; }
    .col-right { text-align: right; }
    .col-actions { text-align: right; width: 1%; white-space: nowrap; }
    .action-cell { display: flex; align-items: center; justify-content: flex-end; gap: 4px; }
    .cancel-devis-btn { color: #c62828 !important; margin-left: auto; }
    .devis-annule-row { opacity: 0.5; }
    .item-montant-crf { color: rgba(0,0,0,0.54); }
    .item-classification { font-size: 12px; color: rgba(0,0,0,0.54); }
    .devis-statut-badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 500; text-transform: uppercase; }
    .devis-statut-en_attente { background: #fff9c4; color: #f9a825; }
    .devis-statut-envoye { background: #e3f2fd; color: #1565c0; }
    .devis-statut-approuve { background: #e8f5e9; color: #2e7d32; }
    .devis-statut-refuse { background: #ffebee; color: #c62828; }
    .devis-statut-annule { background: #eeeeee; color: #616161; }
    .fichier-link { color: #1565c0; text-decoration: none; font-size: 13px; white-space: nowrap; }
    .fichier-link:hover { text-decoration: underline; }

    .approval-btn { }
    .add-facture-btn { font-size: 12px; }
    .approval-form { display: flex; align-items: center; gap: 12px; padding: 12px 0; flex-wrap: wrap; }
    .approval-email-field { min-width: 280px; }
    .valideur-hint { font-size: 12px; color: rgba(0,0,0,0.54); }
    .cc-checkboxes { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; width: 100%; padding: 4px 0; }
    .cc-label { font-size: 13px; font-weight: 500; color: rgba(0,0,0,0.6); }
    .timeline { margin: 8px 0 16px; }
    .timeline-entry { display: flex; gap: 12px; align-items: flex-start; padding: 8px 0; border-left: 2px solid rgba(0,0,0,0.12); margin-left: 12px; padding-left: 16px; position: relative; }
    .timeline-entry::before { content: ''; position: absolute; left: -5px; top: 12px; width: 8px; height: 8px; border-radius: 50%; background: #bdbdbd; }
    .timeline-icon { font-size: 20px; width: 20px; height: 20px; flex-shrink: 0; }
    .timeline-icon-creation { color: #2e7d32; }
    .timeline-icon-cloture { color: #757575; }
    .timeline-icon-reouverture { color: #1565c0; }
    .timeline-icon-annulation { color: #c62828; }
    .timeline-icon-devis_ajoute, .timeline-icon-devis_modifie { color: #1565c0; }
    .timeline-icon-devis_fichier_upload { color: #1565c0; }
    .timeline-icon-dossier_envoye_approbation { color: #ef6c00; }
    .timeline-icon-devis_envoye_approbation, .timeline-icon-devis_renvoye_approbation { color: #ef6c00; }
    .timeline-icon-devis_approuve { color: #2e7d32; }
    .timeline-icon-devis_refuse, .timeline-icon-devis_annule { color: #c62828; }
    .timeline-icon-facture_ajoutee, .timeline-icon-facture_modifiee { color: #1565c0; }
    .timeline-icon-modification { color: #1565c0; }
    .timeline-content { display: flex; flex-direction: column; gap: 2px; }
    .timeline-date { font-size: 12px; color: rgba(0,0,0,0.54); }
    .timeline-details { font-size: 14px; }
    .timeline-auteur { font-size: 12px; color: rgba(0,0,0,0.54); }
    .col-numero { white-space: nowrap; font-weight: 500; }
    .facture-detail-view { margin: 12px 0; }
    .facture-detail-view p { margin: 4px 0; }
    .form-actions { display: flex; gap: 8px; justify-content: flex-end; }
  `],
})
export class DossierDetailComponent implements OnInit, OnChanges {
  @Input() dt!: string;
  @Input() immat!: string;
  @Input() numero!: string;
  @Output() back = new EventEmitter<void>();

  private readonly repairService = inject(RepairService);
  private readonly valideurService = inject(ValideurService);
  private readonly contactCCService = inject(ContactCCService);
  private readonly snackBar = inject(MatSnackBar);
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly dialog = inject(MatDialog);

  @ViewChild(MatAutocompleteTrigger) valideurAutoTrigger!: MatAutocompleteTrigger;

  dossier: DossierReparation | null = null;
  loading = false;
  actionLoading = false;
  showDevisForm = false;
  showFactureForm = false;
  editingDevis: Devis | null = null;
  approvalDevis: Devis | null = null;
  approvalEmail = '';
  approvalLoading = false;
  isResend = false;
  bulkApprovalMode = false;
  historique: AuditEntry[] = [];
  historiqueLoading = false;
  preselectedDevisId: string | null = null;
  factureDevisLabel: string | null = null;
  editingFacture: Facture | null = null;
  viewingFacture: Facture | null = null;

  // Valideur selector
  valideurSearchControl = new FormControl('');
  valideurs: Valideur[] = [];
  filteredValideurs$!: Observable<Valideur[]>;

  // Contacts CC
  contactsCC: ContactCC[] = [];
  selectedCCEmails: Set<string> = new Set();

  ngOnInit(): void {
    this.loadDossier();
    this.loadHistorique();
    this.loadValideurs();
    this.loadContactsCC();
    this.filteredValideurs$ = this.valideurSearchControl.valueChanges.pipe(
      startWith(''),
      map(value => {
        const searchStr = typeof value === 'string' ? value : (value as any)?.nom || '';
        return this.filterValideurs(searchStr);
      })
    );
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['numero'] && !changes['numero'].firstChange) {
      this.loadDossier();
    }
  }

  loadHistorique(): void {
    if (!this.dt || !this.immat || !this.numero) return;
    this.historiqueLoading = true;
    this.repairService.getHistorique(this.dt, this.immat, this.numero).subscribe({
      next: (entries) => { this.historique = entries; this.historiqueLoading = false; this.cdr.detectChanges(); },
      error: () => { this.historiqueLoading = false; this.cdr.detectChanges(); },
    });
  }

  actionIcon(action: string): string {
    const icons: Record<string, string> = {
      creation: 'add_circle',
      cloture: 'lock',
      reouverture: 'lock_open',
      annulation: 'cancel',
      modification: 'edit',
      devis_ajoute: 'description',
      devis_modifie: 'description',
      dossier_envoye_approbation: 'playlist_add_check',
      devis_envoye_approbation: 'send',
      devis_renvoye_approbation: 'replay',
      devis_approuve: 'check_circle',
      devis_refuse: 'block',
      devis_annule: 'block',
      devis_fichier_upload: 'upload_file',
      facture_fichier_upload: 'upload_file',
      facture_ajoutee: 'receipt',
      facture_modifiee: 'receipt',
    };
    return icons[action] || 'info';
  }

  loadDossier(): void {
    if (!this.dt || !this.immat || !this.numero) return;
    this.loading = true;
    this.repairService.getDossier(this.dt, this.immat, this.numero).subscribe({
      next: (d) => { this.dossier = d; this.loading = false; this.cdr.detectChanges(); },
      error: () => {
        this.snackBar.open('Erreur lors du chargement du dossier', 'Fermer', { duration: 5000 });
        this.loading = false;
        this.cdr.detectChanges();
      },
    });
  }

  updateStatut(statut: 'ouvert' | 'cloture' | 'annule'): void {
    if (!this.dossier) return;
    this.actionLoading = true;
    this.repairService.updateDossier(this.dt, this.immat, this.dossier.numero, { statut }).subscribe({
      next: (d) => {
        this.dossier = d;
        this.actionLoading = false;
        this.snackBar.open('Statut mis à jour', 'Fermer', { duration: 3000 });
        this.cdr.detectChanges();
        this.loadHistorique();
      },
      error: () => {
        this.actionLoading = false;
        this.snackBar.open('Erreur lors de la mise à jour du statut', 'Fermer', { duration: 5000 });
        this.cdr.detectChanges();
      },
    });
  }

  statutLabel(statut: string): string {
    switch (statut) {
      case 'ouvert': return 'Ouvert';
      case 'cloture': return 'Clôturé';
      case 'annule': return 'Annulé';
      default: return statut;
    }
  }

  devisStatutLabel(statut: string): string {
    switch (statut) {
      case 'en_attente': return 'En attente';
      case 'envoye': return 'Envoyé';
      case 'approuve': return 'Approuvé';
      case 'refuse': return 'Refusé';
      case 'annule': return 'Annulé';
      default: return statut;
    }
  }

  classificationLabel(classification: string): string {
    const labels: Record<string, string> = {
      entretien_courant: 'Entretien courant',
      reparation_carrosserie_mecanique: 'Carrosserie / mécanique',
      reparation_sanitaire: 'Sanitaire',
      reparation_marquage: 'Marquage',
      controle_technique: 'Contrôle technique',
      frais_duplicata_carte_grise: 'Duplicata carte grise',
      autre: 'Autre',
    };
    return labels[classification] || classification;
  }

  onDevisCreated(_devis: Devis): void {
    this.showDevisForm = false;
    this.loadDossier();
    this.loadHistorique();
  }

  startEditDevis(devis: Devis): void {
    this.editingDevis = devis;
  }

  onDevisUpdated(_devis: Devis): void {
    this.editingDevis = null;
    this.loadDossier();
    this.loadHistorique();
  }

  onFactureCreated(_facture: FactureCreateResponse): void {
    this.showFactureForm = false;
    this.preselectedDevisId = null;
    this.factureDevisLabel = null;
    this.editingFacture = null;
    this.loadDossier();
    this.loadHistorique();
  }

  onFactureCancelled(): void {
    this.showFactureForm = false;
    this.preselectedDevisId = null;
    this.factureDevisLabel = null;
    this.editingFacture = null;
  }

  createFactureForDevis(devis: Devis): void {
    this.preselectedDevisId = String(devis.id);
    this.factureDevisLabel = `Devis ${this.padId(devis.id)}`;
    this.editingFacture = null;
    this.viewingFacture = null;
    this.showFactureForm = true;
  }

  getFactureForDevis(devisId: string): Facture | undefined {
    return this.dossier?.factures?.find(f => f.devis_id === devisId);
  }

  viewFactureForDevis(devis: Devis): void {
    const facture = this.getFactureForDevis(devis.id);
    if (facture) {
      this.viewingFacture = facture;
      this.showFactureForm = false;
    }
  }

  startEditFacture(facture: Facture): void {
    this.editingFacture = facture;
    this.viewingFacture = null;
    this.preselectedDevisId = facture.devis_id || null;
    this.factureDevisLabel = facture.devis_id ? `Devis ${this.padId(facture.devis_id)}` : null;
    this.showFactureForm = true;
  }

  padId(id: string): string {
    return id.padStart(2, '0');
  }



  getDevisDescriptionItems(): string[] {
    if (!this.preselectedDevisId || !this.dossier) return [];
    const devis = this.dossier.devis?.find(d => String(d.id) === this.preselectedDevisId);
    return devis?.description_items || this.dossier.description || [];
  }

  getDevisDescriptionTravaux(): string {
    if (!this.preselectedDevisId || !this.dossier) return '';
    const devis = this.dossier.devis?.find(d => String(d.id) === this.preselectedDevisId);
    return devis?.description_travaux || devis?.description || '';
  }

  private loadValideurs(): void {
    if (!this.dt) return;
    this.valideurService.listValideurs(this.dt).subscribe({
      next: (res) => {
        this.valideurs = (res.valideurs || []).filter(v => v.actif);
        this.cdr.detectChanges();
      },
    });
  }

  private loadContactsCC(): void {
    if (!this.dt) return;
    this.contactCCService.listContactsCC(this.dt).subscribe({
      next: (res) => {
        this.contactsCC = (res.contacts_cc || []).filter(c => c.actif);
        this.cdr.detectChanges();
      },
    });
  }

  private prefillPrincipalValideur(): void {
    const principal = this.valideurs.find(v => v.principal);
    if (principal) {
      this.approvalEmail = principal.email;
      this.valideurSearchControl.setValue(`${principal.prenom} ${principal.nom}`);
    }
  }

  private prefillDefaultCC(): void {
    this.selectedCCEmails = new Set(
      this.contactsCC.filter(c => c.cc_par_defaut).map(c => c.email)
    );
  }

  toggleCC(email: string): void {
    if (this.selectedCCEmails.has(email)) {
      this.selectedCCEmails.delete(email);
    } else {
      this.selectedCCEmails.add(email);
    }
  }

  isCCSelected(email: string): boolean {
    return this.selectedCCEmails.has(email);
  }

  private filterValideurs(search: string): Valideur[] {
    if (!search) return this.valideurs;
    const lower = search.toLowerCase();
    return this.valideurs.filter(v =>
      v.prenom.toLowerCase().includes(lower) || v.nom.toLowerCase().includes(lower) || v.email.toLowerCase().includes(lower)
    );
  }

  displayValideurFn(valideur: Valideur | string): string {
    if (!valideur) return '';
    if (typeof valideur === 'string') return valideur;
    return `${valideur.prenom} ${valideur.nom}`;
  }

  onValideurSelected(valideur: Valideur): void {
    this.approvalEmail = valideur.email;
  }

  onValideurFocus(): void {
    if (!this.valideurSearchControl.value || this.valideurSearchControl.value === '') {
      this.valideurSearchControl.setValue('');
      setTimeout(() => this.valideurAutoTrigger?.openPanel());
    }
  }

  toggleValideurPanel(event: Event): void {
    event.stopPropagation();
    if (this.valideurAutoTrigger.panelOpen) {
      this.valideurAutoTrigger.closePanel();
    } else {
      this.valideurSearchControl.setValue('');
      this.valideurAutoTrigger.openPanel();
    }
  }

  openApprovalForm(devis: Devis, prefillValideur?: string): void {
    this.approvalDevis = devis;
    this.isResend = devis.statut === 'envoye' || devis.statut === 'refuse';
    this.prefillDefaultCC();
    if (prefillValideur) {
      this.approvalEmail = prefillValideur;
      const found = this.valideurs.find(v => v.email === prefillValideur);
      this.valideurSearchControl.setValue(found ? `${found.prenom} ${found.nom}` : prefillValideur);
    } else {
      this.prefillPrincipalValideur();
      if (!this.approvalEmail) {
        this.approvalEmail = '';
        this.valideurSearchControl.setValue('');
      }
    }
  }

  confirmResend(devis: Devis): void {
    const dateEnvoi = devis.date_envoi_approbation
      ? new Date(devis.date_envoi_approbation).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
      : 'date inconnue';

    let message: string;
    if (devis.statut === 'refuse') {
      message = `Ce devis a été refusé par ${devis.valideur_email || 'le valideur'}. Voulez-vous renvoyer la demande d'approbation ?`;
    } else {
      message = `Un email d'approbation a déjà été envoyé à ${devis.valideur_email || 'le valideur'} le ${dateEnvoi}. Voulez-vous renvoyer la demande ? Un nouveau lien sera généré (l'ancien sera invalidé).`;
    }

    const dialogRef = this.dialog.open(ConfirmResendDialogComponent, {
      width: '480px',
      data: { message },
    });

    dialogRef.afterClosed().subscribe((confirmed: boolean) => {
      if (confirmed) {
        this.openApprovalForm(devis, devis.valideur_email || undefined);
      }
    });
  }

  sendForApproval(): void {
    if (!this.approvalDevis || !this.approvalEmail || !this.dossier) return;
    this.approvalLoading = true;
    const isResend = this.isResend;
    const ccEmails = Array.from(this.selectedCCEmails);
    this.repairService.sendApproval(
      this.dt, this.immat, this.dossier.numero,
      String(this.approvalDevis.id),
      { valideur_email: this.approvalEmail, cc_emails: ccEmails.length > 0 ? ccEmails : undefined }
    ).subscribe({
      next: () => {
        this.approvalLoading = false;
        this.approvalDevis = null;
        this.isResend = false;
        const msg = isResend ? 'Devis renvoyé pour approbation' : 'Devis envoyé pour approbation';
        this.snackBar.open(msg, 'Fermer', { duration: 5000 });
        this.cdr.detectChanges();
        this.loadDossier();
        this.loadHistorique();
      },
      error: () => {
        this.approvalLoading = false;
        this.snackBar.open('Erreur lors de l\'envoi pour approbation', 'Fermer', { duration: 5000 });
        this.cdr.detectChanges();
      },
    });
  }

  hasPendingDevis(): boolean {
    return !!this.dossier?.devis?.some(d => d.statut === 'en_attente');
  }

  openBulkApprovalForm(): void {
    this.bulkApprovalMode = true;
    this.prefillDefaultCC();
    this.prefillPrincipalValideur();
    if (!this.approvalEmail) {
      this.approvalEmail = '';
      this.valideurSearchControl.setValue('');
    }
  }

  sendBulkApproval(): void {
    if (!this.approvalEmail || !this.dossier) return;
    this.approvalLoading = true;
    const ccEmails = Array.from(this.selectedCCEmails);
    this.repairService.sendBulkApproval(
      this.dt, this.immat, this.dossier.numero,
      { valideur_email: this.approvalEmail, cc_emails: ccEmails.length > 0 ? ccEmails : undefined }
    ).subscribe({
      next: (res) => {
        this.approvalLoading = false;
        this.bulkApprovalMode = false;
        this.snackBar.open(res.message || 'Devis envoyés pour approbation', 'Fermer', { duration: 5000 });
        this.cdr.detectChanges();
        this.loadDossier();
        this.loadHistorique();
      },
      error: () => {
        this.approvalLoading = false;
        this.snackBar.open('Erreur lors de l\'envoi groupé pour approbation', 'Fermer', { duration: 5000 });
        this.cdr.detectChanges();
      },
    });
  }

  annulerDevis(devis: Devis): void {
    if (!this.dossier) return;
    const message = `Voulez-vous annuler le devis #${devis.id} de ${devis.fournisseur?.nom || 'ce fournisseur'} (${devis.montant.toFixed(2)} €) ? Cette action est irréversible.`;
    const dialogRef = this.dialog.open(ConfirmCancelDevisDialogComponent, {
      width: '420px',
      data: { message },
    });
    dialogRef.afterClosed().subscribe((confirmed: boolean) => {
      if (confirmed) {
        this.actionLoading = true;
        this.repairService.annulerDevis(this.dt, this.immat, this.dossier!.numero, String(devis.id)).subscribe({
          next: () => {
            this.actionLoading = false;
            this.snackBar.open('Devis annulé', 'Fermer', { duration: 3000 });
            this.loadDossier();
            this.loadHistorique();
            this.cdr.detectChanges();
          },
          error: (err) => {
            this.actionLoading = false;
            this.snackBar.open(err?.error?.detail || 'Erreur lors de l\'annulation', 'Fermer', { duration: 5000 });
            this.cdr.detectChanges();
          },
        });
      }
    });
  }
}
