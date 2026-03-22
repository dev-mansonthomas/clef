import { Component, Input, OnInit, inject, signal, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatTableModule } from '@angular/material/table';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { FournisseurService } from '../../services/fournisseur.service';
import {
  Fournisseur,
  CreateFournisseurRequest,
  UpdateFournisseurRequest,
} from '../../models/repair.model';

@Component({
  selector: 'app-fournisseurs-manager',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatTableModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatSnackBarModule,
  ],
  templateUrl: './fournisseurs-manager.component.html',
  styleUrl: './fournisseurs-manager.component.scss',
})
export class FournisseursManagerComponent implements OnInit {
  @Input() dt = '';
  @Input() niveau: 'dt' | 'ul' = 'dt';

  private readonly fournisseurService = inject(FournisseurService);
  private readonly snackBar = inject(MatSnackBar);
  private readonly cdr = inject(ChangeDetectorRef);

  fournisseurs = signal<Fournisseur[]>([]);
  loading = signal(false);
  showForm = signal(false);
  editingId = signal<string | null>(null);

  displayedColumns = ['nom', 'telephone', 'email', 'ville', 'numero_contrat', 'statut', 'actions'];

  // Form fields
  formNom = '';
  formTelephone = '';
  formEmail = '';
  formAdresseRue = '';
  formCodePostal = '';
  formVille = '';
  formNumeroContrat = '';

  ngOnInit(): void {
    if (this.dt) {
      this.loadFournisseurs();
    }
  }

  loadFournisseurs(): void {
    this.loading.set(true);
    this.fournisseurService.listFournisseurs(this.dt).subscribe({
      next: (response) => {
        this.fournisseurs.set(response.fournisseurs);
        this.loading.set(false);
        this.cdr.markForCheck();
      },
      error: (err) => {
        console.error('Error loading fournisseurs:', err);
        this.snackBar.open('Erreur lors du chargement des fournisseurs', 'Fermer', { duration: 3000 });
        this.loading.set(false);
      },
    });
  }

  toggleForm(): void {
    this.showForm.set(!this.showForm());
    if (!this.showForm()) {
      this.resetForm();
    }
  }

  resetForm(): void {
    this.formNom = '';
    this.formTelephone = '';
    this.formEmail = '';
    this.formAdresseRue = '';
    this.formCodePostal = '';
    this.formVille = '';
    this.formNumeroContrat = '';
    this.editingId.set(null);
  }

  editFournisseur(f: Fournisseur): void {
    this.editingId.set(f.id);
    this.formNom = f.nom;
    this.formTelephone = f.telephone ?? '';
    this.formEmail = f.email ?? '';
    this.formAdresseRue = f.adresse_rue ?? '';
    this.formCodePostal = f.adresse_code_postal ?? '';
    this.formVille = f.adresse_ville ?? '';
    this.formNumeroContrat = f.numero_contrat ?? '';
    this.showForm.set(true);
  }

  saveFournisseur(): void {
    if (!this.formNom.trim()) {
      this.snackBar.open('Le nom est requis', 'Fermer', { duration: 3000 });
      return;
    }

    const editId = this.editingId();
    if (editId) {
      const data: UpdateFournisseurRequest = {
        nom: this.formNom.trim(),
        telephone: this.formTelephone.trim() || undefined,
        email: this.formEmail.trim() || undefined,
        adresse_rue: this.formAdresseRue.trim() || undefined,
        adresse_code_postal: this.formCodePostal.trim() || undefined,
        adresse_ville: this.formVille.trim() || undefined,
        numero_contrat: this.formNumeroContrat.trim() || undefined,
      };
      this.fournisseurService.updateFournisseur(this.dt, editId, data).subscribe({
        next: () => {
          this.snackBar.open('Fournisseur mis à jour', 'Fermer', { duration: 3000 });
          this.resetForm();
          this.showForm.set(false);
          this.loadFournisseurs();
        },
        error: (err) => {
          console.error('Error updating fournisseur:', err);
          this.snackBar.open('Erreur lors de la mise à jour', 'Fermer', { duration: 3000 });
        },
      });
    } else {
      const data: CreateFournisseurRequest = {
        nom: this.formNom.trim(),
        telephone: this.formTelephone.trim() || undefined,
        email: this.formEmail.trim() || undefined,
        adresse_rue: this.formAdresseRue.trim() || undefined,
        adresse_code_postal: this.formCodePostal.trim() || undefined,
        adresse_ville: this.formVille.trim() || undefined,
        numero_contrat: this.formNumeroContrat.trim() || undefined,
        niveau: this.niveau,
      };
      this.fournisseurService.createFournisseur(this.dt, data).subscribe({
        next: () => {
          this.snackBar.open('Fournisseur créé', 'Fermer', { duration: 3000 });
          this.resetForm();
          this.showForm.set(false);
          this.loadFournisseurs();
        },
        error: (err) => {
          console.error('Error creating fournisseur:', err);
          this.snackBar.open('Erreur lors de la création', 'Fermer', { duration: 3000 });
        },
      });
    }
  }

  toggleArchive(f: Fournisseur): void {
    const data: UpdateFournisseurRequest = { archive: !f.archive };
    this.fournisseurService.updateFournisseur(this.dt, f.id, data).subscribe({
      next: () => {
        const label = f.archive ? 'réactivé' : 'archivé';
        this.snackBar.open(`Fournisseur ${label}`, 'Fermer', { duration: 3000 });
        this.loadFournisseurs();
      },
      error: (err) => {
        console.error('Error toggling archive:', err);
        this.snackBar.open('Erreur lors de la mise à jour', 'Fermer', { duration: 3000 });
      },
    });
  }
}
