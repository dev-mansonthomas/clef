import { Component, Input, Output, EventEmitter, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormControl } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
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
    </div>
  `,
  styles: [`
    .full-width { width: 100%; }
    .hint { color: rgba(0,0,0,0.54); font-size: 12px; }
  `],
})
export class FournisseurSelectorComponent implements OnInit {
  @Input() dt!: string;
  @Output() fournisseurSelected = new EventEmitter<Fournisseur>();

  private readonly fournisseurService = inject(FournisseurService);

  searchControl = new FormControl('');
  fournisseurs: Fournisseur[] = [];
  filteredFournisseurs$!: Observable<Fournisseur[]>;

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
      next: (res) => {
        // Filter out archived fournisseurs — they should not be selectable
        this.fournisseurs = (res.fournisseurs || []).filter(f => !f.archive);
      },
    });
  }

  private filterFournisseurs(search: string): Fournisseur[] {
    const lower = search.toLowerCase();
    return this.fournisseurs.filter(f => f.nom.toLowerCase().includes(lower));
  }

  onSelected(fournisseur: Fournisseur): void {
    this.fournisseurSelected.emit(fournisseur);
  }
}

