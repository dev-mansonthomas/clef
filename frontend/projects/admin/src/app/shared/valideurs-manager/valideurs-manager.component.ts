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
import { ValideurService } from '../../services/valideur.service';
import {
  Valideur,
  CreateValideurRequest,
  UpdateValideurRequest,
} from '../../models/repair.model';

@Component({
  selector: 'app-valideurs-manager',
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
  templateUrl: './valideurs-manager.component.html',
  styleUrl: './valideurs-manager.component.scss',
})
export class ValideursManagerComponent implements OnInit {
  @Input() dt = '';
  @Input() niveau: 'dt' | 'ul' = 'dt';

  private readonly valideurService = inject(ValideurService);
  private readonly snackBar = inject(MatSnackBar);
  private readonly cdr = inject(ChangeDetectorRef);

  valideurs = signal<Valideur[]>([]);
  loading = signal(false);
  showForm = signal(false);
  editingId = signal<string | null>(null);

  displayedColumns = ['nom', 'role', 'statut', 'actions'];

  // Form fields
  formPrenom = '';
  formNom = '';
  formEmail = '';
  formRole = '';

  ngOnInit(): void {
    if (this.dt) {
      this.loadValideurs();
    }
  }

  loadValideurs(): void {
    this.loading.set(true);
    this.valideurService.listValideurs(this.dt).subscribe({
      next: (response) => {
        this.valideurs.set(response.valideurs);
        this.loading.set(false);
        this.cdr.markForCheck();
      },
      error: (err) => {
        console.error('Error loading valideurs:', err);
        this.snackBar.open('Erreur lors du chargement des valideurs', 'Fermer', { duration: 3000 });
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
    this.formPrenom = '';
    this.formNom = '';
    this.formEmail = '';
    this.formRole = '';
    this.editingId.set(null);
  }

  editValideur(v: Valideur): void {
    this.editingId.set(v.id);
    this.formPrenom = v.prenom;
    this.formNom = v.nom;
    this.formEmail = v.email;
    this.formRole = v.role ?? '';
    this.showForm.set(true);
  }

  saveValideur(): void {
    if (!this.formPrenom.trim() || !this.formNom.trim() || !this.formEmail.trim()) {
      this.snackBar.open('Le prénom, le nom et l\'email sont requis', 'Fermer', { duration: 3000 });
      return;
    }

    const editId = this.editingId();
    if (editId) {
      const data: UpdateValideurRequest = {
        prenom: this.formPrenom.trim(),
        nom: this.formNom.trim(),
        email: this.formEmail.trim(),
        role: this.formRole.trim() || undefined,
      };
      this.valideurService.updateValideur(this.dt, editId, data).subscribe({
        next: () => {
          this.snackBar.open('Valideur mis à jour', 'Fermer', { duration: 3000 });
          this.resetForm();
          this.showForm.set(false);
          this.loadValideurs();
        },
        error: (err) => {
          console.error('Error updating valideur:', err);
          this.snackBar.open('Erreur lors de la mise à jour', 'Fermer', { duration: 3000 });
        },
      });
    } else {
      const data: CreateValideurRequest = {
        prenom: this.formPrenom.trim(),
        nom: this.formNom.trim(),
        email: this.formEmail.trim(),
        role: this.formRole.trim() || undefined,
        niveau: this.niveau,
      };
      this.valideurService.createValideur(this.dt, data).subscribe({
        next: () => {
          this.snackBar.open('Valideur créé', 'Fermer', { duration: 3000 });
          this.resetForm();
          this.showForm.set(false);
          this.loadValideurs();
        },
        error: (err) => {
          console.error('Error creating valideur:', err);
          this.snackBar.open('Erreur lors de la création', 'Fermer', { duration: 3000 });
        },
      });
    }
  }

  toggleActif(v: Valideur): void {
    const data: UpdateValideurRequest = { actif: !v.actif };
    this.valideurService.updateValideur(this.dt, v.id, data).subscribe({
      next: () => {
        const label = v.actif ? 'désactivé' : 'activé';
        this.snackBar.open(`Valideur ${label}`, 'Fermer', { duration: 3000 });
        this.loadValideurs();
      },
      error: (err) => {
        console.error('Error toggling actif:', err);
        this.snackBar.open('Erreur lors de la mise à jour', 'Fermer', { duration: 3000 });
      },
    });
  }
}

