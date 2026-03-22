import { Component, Input, Output, EventEmitter, OnInit, inject, ViewChild, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormControl } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatAutocompleteModule, MatAutocompleteTrigger } from '@angular/material/autocomplete';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
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
    MatIconModule,
    MatButtonModule,
  ],
  template: `
    <div class="fournisseur-selector">
      <mat-form-field appearance="outline" class="full-width">
        <mat-label>Fournisseur</mat-label>
        <input matInput [formControl]="searchControl" [matAutocomplete]="auto"
               placeholder="Rechercher un fournisseur…"
               (focus)="onFocus()">
        <button mat-icon-button matSuffix type="button" (click)="togglePanel($event)" tabindex="-1">
          <mat-icon>arrow_drop_down</mat-icon>
        </button>
        <mat-autocomplete #auto="matAutocomplete" [displayWith]="displayFn" (optionSelected)="onSelected($event.option.value)">
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

  @ViewChild(MatAutocompleteTrigger) autoTrigger!: MatAutocompleteTrigger;

  private readonly fournisseurService = inject(FournisseurService);
  private readonly cdr = inject(ChangeDetectorRef);

  searchControl = new FormControl('');
  fournisseurs: Fournisseur[] = [];
  filteredFournisseurs$!: Observable<Fournisseur[]>;

  ngOnInit(): void {
    this.loadFournisseurs();
    this.filteredFournisseurs$ = this.searchControl.valueChanges.pipe(
      startWith(''),
      map(value => {
        const searchStr = typeof value === 'string' ? value : (value as any)?.nom || '';
        return this.filterFournisseurs(searchStr);
      })
    );
  }

  private loadFournisseurs(): void {
    if (!this.dt) return;
    this.fournisseurService.listFournisseurs(this.dt).subscribe({
      next: (res) => {
        // Filter out archived fournisseurs — they should not be selectable
        this.fournisseurs = (res.fournisseurs || []).filter(f => !f.archive);
        this.cdr.detectChanges();
      },
    });
  }

  private filterFournisseurs(search: string): Fournisseur[] {
    if (!search) return this.fournisseurs;
    const lower = search.toLowerCase();
    return this.fournisseurs.filter(f => f.nom.toLowerCase().includes(lower));
  }

  displayFn(fournisseur: Fournisseur | string): string {
    if (!fournisseur) return '';
    if (typeof fournisseur === 'string') return fournisseur;
    return fournisseur.nom;
  }

  onFocus(): void {
    if (!this.searchControl.value || this.searchControl.value === '') {
      this.searchControl.setValue('');
      setTimeout(() => this.autoTrigger?.openPanel());
    }
  }

  togglePanel(event: Event): void {
    event.stopPropagation();
    if (this.autoTrigger.panelOpen) {
      this.autoTrigger.closePanel();
    } else {
      this.searchControl.setValue('');
      this.autoTrigger.openPanel();
    }
  }

  onSelected(fournisseur: Fournisseur): void {
    this.fournisseurSelected.emit(fournisseur);
  }
}

