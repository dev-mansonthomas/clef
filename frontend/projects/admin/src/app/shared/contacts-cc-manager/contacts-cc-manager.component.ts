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
import { ContactCCService } from '../../services/contact-cc.service';
import {
  ContactCC,
  CreateContactCCRequest,
  UpdateContactCCRequest,
} from '../../models/repair.model';

@Component({
  selector: 'app-contacts-cc-manager',
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
  templateUrl: './contacts-cc-manager.component.html',
  styleUrl: './contacts-cc-manager.component.scss',
})
export class ContactsCCManagerComponent implements OnInit {
  @Input() dt = '';
  @Input() niveau: 'dt' | 'ul' = 'dt';

  private readonly contactCCService = inject(ContactCCService);
  private readonly snackBar = inject(MatSnackBar);
  private readonly cdr = inject(ChangeDetectorRef);

  contacts = signal<ContactCC[]>([]);
  loading = signal(false);
  showForm = signal(false);
  editingId = signal<string | null>(null);

  displayedColumns = ['nom', 'role', 'cc_par_defaut', 'statut', 'actions'];

  // Form fields
  formPrenom = '';
  formNom = '';
  formEmail = '';
  formRole = '';

  ngOnInit(): void {
    if (this.dt) {
      this.loadContacts();
    }
  }

  loadContacts(): void {
    this.loading.set(true);
    this.contactCCService.listContactsCC(this.dt).subscribe({
      next: (response) => {
        this.contacts.set(response.contacts_cc);
        this.loading.set(false);
        this.cdr.markForCheck();
      },
      error: (err) => {
        console.error('Error loading contacts CC:', err);
        this.snackBar.open('Erreur lors du chargement des contacts CC', 'Fermer', { duration: 3000 });
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

  editContact(c: ContactCC): void {
    this.editingId.set(c.id);
    this.formPrenom = c.prenom;
    this.formNom = c.nom;
    this.formEmail = c.email;
    this.formRole = c.role ?? '';
    this.showForm.set(true);
  }

  saveContact(): void {
    if (!this.formPrenom.trim() || !this.formNom.trim() || !this.formEmail.trim()) {
      this.snackBar.open('Le prénom, le nom et l\'email sont requis', 'Fermer', { duration: 3000 });
      return;
    }

    const editId = this.editingId();
    if (editId) {
      const data: UpdateContactCCRequest = {
        prenom: this.formPrenom.trim(),
        nom: this.formNom.trim(),
        email: this.formEmail.trim(),
        role: this.formRole.trim() || undefined,
      };
      this.contactCCService.updateContactCC(this.dt, editId, data).subscribe({
        next: () => {
          this.snackBar.open('Contact CC mis à jour', 'Fermer', { duration: 3000 });
          this.resetForm();
          this.showForm.set(false);
          this.loadContacts();
        },
        error: (err) => {
          console.error('Error updating contact CC:', err);
          this.snackBar.open('Erreur lors de la mise à jour', 'Fermer', { duration: 3000 });
        },
      });
    } else {
      const data: CreateContactCCRequest = {
        prenom: this.formPrenom.trim(),
        nom: this.formNom.trim(),
        email: this.formEmail.trim(),
        role: this.formRole.trim() || undefined,
        niveau: this.niveau,
      };
      this.contactCCService.createContactCC(this.dt, data).subscribe({
        next: () => {
          this.snackBar.open('Contact CC créé', 'Fermer', { duration: 3000 });
          this.resetForm();
          this.showForm.set(false);
          this.loadContacts();
        },
        error: (err) => {
          console.error('Error creating contact CC:', err);
          this.snackBar.open('Erreur lors de la création', 'Fermer', { duration: 3000 });
        },
      });
    }
  }

  toggleActif(c: ContactCC): void {
    const data: UpdateContactCCRequest = { actif: !c.actif };
    this.contactCCService.updateContactCC(this.dt, c.id, data).subscribe({
      next: () => {
        const label = c.actif ? 'désactivé' : 'activé';
        this.snackBar.open(`Contact CC ${label}`, 'Fermer', { duration: 3000 });
        this.loadContacts();
      },
      error: (err) => {
        console.error('Error toggling actif:', err);
        this.snackBar.open('Erreur lors de la mise à jour', 'Fermer', { duration: 3000 });
      },
    });
  }

  toggleCCParDefaut(c: ContactCC): void {
    const data: UpdateContactCCRequest = { cc_par_defaut: !c.cc_par_defaut };
    this.contactCCService.updateContactCC(this.dt, c.id, data).subscribe({
      next: () => {
        const label = c.cc_par_defaut ? 'retiré du CC par défaut' : 'ajouté au CC par défaut';
        this.snackBar.open(`Contact ${label}`, 'Fermer', { duration: 3000 });
        this.loadContacts();
      },
      error: (err) => {
        console.error('Error toggling cc_par_defaut:', err);
        this.snackBar.open('Erreur lors de la mise à jour', 'Fermer', { duration: 3000 });
      },
    });
  }
}

