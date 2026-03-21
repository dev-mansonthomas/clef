import { Component, Input, Output, EventEmitter, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormControl, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { Observable, startWith, map } from 'rxjs';
import { FournisseurService } from '../../services/fournisseur.service';
import { Fournisseur } from '../../models/repair.model';

@Component({
  selector: 'app-fournisseur-selector',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatAutocompleteModule,
    MatButtonModule,
    MatIconModule,
    MatSnackBarModule,
    MatProgressSpinnerModule,
  ],
  template: `
    <div class="fournisseur-selector">
      <mat-form-field appearance="outline" class="full-width">
        <mat-label>Fournisseur</mat-label>
        <input matInput [formControl]="searchControl" [matAutocomplete]="auto" placeholder="Rechercher un fournisseur…">
        <mat-autocomplete #auto="matAutocomplete" (optionSelected)="onSelected($event.option.value)">
          <mat-option *ngFor="let f of filteredFournisseurs$ | async" [value]="f">
            {{ f.nom }} <span *ngIf="f.telephone" class="hint"> — {{ f.telephone }}</span>
          </mat-option>
        </mat-autocomplete>
      </mat-form-field>

      <button mat-stroked-button type="button" (click)="showAddForm = !showAddForm">
        <mat-icon>{{ showAddForm ? 'close' : 'add' }}</mat-icon>
        {{ showAddForm ? 'Annuler' : 'Ajouter un fournisseur' }}
      </button>

      <div *ngIf="showAddForm" class="add-form">
        <form [formGroup]="addForm" (ngSubmit)="onAddFournisseur()">
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Nom</mat-label>
            <input matInput formControlName="nom">
            <mat-error *ngIf="addForm.get('nom')?.hasError('required')">Le nom est requis</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Téléphone</mat-label>
            <input matInput formControlName="telephone">
          </mat-form-field>
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Email</mat-label>
            <input matInput formControlName="email" type="email">
          </mat-form-field>
          <button mat-raised-button color="primary" type="submit" [disabled]="addForm.invalid || addingFournisseur">
            {{ addingFournisseur ? 'Ajout…' : 'Ajouter' }}
          </button>
        </form>
      </div>
    </div>
  `,
  styles: [`
    .full-width { width: 100%; }
    .hint { color: rgba(0,0,0,0.54); font-size: 12px; }
    .add-form { margin-top: 12px; padding: 12px; border: 1px solid rgba(0,0,0,0.12); border-radius: 8px; }
  `],
})
export class FournisseurSelectorComponent implements OnInit {
  @Input() dt!: string;
  @Output() fournisseurSelected = new EventEmitter<Fournisseur>();

  private readonly fournisseurService = inject(FournisseurService);
  private readonly fb = inject(FormBuilder);
  private readonly snackBar = inject(MatSnackBar);

  searchControl = new FormControl('');
  fournisseurs: Fournisseur[] = [];
  filteredFournisseurs$!: Observable<Fournisseur[]>;
  showAddForm = false;
  addingFournisseur = false;

  addForm = this.fb.group({
    nom: ['', Validators.required],
    telephone: [''],
    email: [''],
  });

  ngOnInit(): void {
    this.loadFournisseurs();
    this.filteredFournisseurs$ = this.searchControl.valueChanges.pipe(
      startWith(''),
      map(value => this.filterFournisseurs(typeof value === 'string' ? value : ''))
    );
  }

  private loadFournisseurs(): void {
    if (!this.dt) return;
    this.fournisseurService.listFournisseurs(this.dt).subscribe({
      next: (res) => { this.fournisseurs = res.fournisseurs || []; },
    });
  }

  private filterFournisseurs(search: string): Fournisseur[] {
    const lower = search.toLowerCase();
    return this.fournisseurs.filter(f => f.nom.toLowerCase().includes(lower));
  }

  onSelected(fournisseur: Fournisseur): void {
    this.fournisseurSelected.emit(fournisseur);
  }

  onAddFournisseur(): void {
    if (this.addForm.invalid) return;
    this.addingFournisseur = true;
    const data = {
      nom: this.addForm.value.nom!,
      telephone: this.addForm.value.telephone || undefined,
      email: this.addForm.value.email || undefined,
      scope: 'dt' as const,
    };
    this.fournisseurService.createFournisseur(this.dt, data).subscribe({
      next: (f) => {
        this.fournisseurs.push(f);
        this.fournisseurSelected.emit(f);
        this.showAddForm = false;
        this.addForm.reset();
        this.addingFournisseur = false;
        this.snackBar.open('Fournisseur ajouté', 'Fermer', { duration: 3000 });
      },
      error: () => {
        this.addingFournisseur = false;
        this.snackBar.open('Erreur lors de l\'ajout du fournisseur', 'Fermer', { duration: 5000 });
      },
    });
  }
}

