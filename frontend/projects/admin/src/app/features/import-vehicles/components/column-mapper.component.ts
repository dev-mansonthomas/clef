import { Component, Input, Output, EventEmitter, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatTableModule } from '@angular/material/table';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

interface TargetField {
  key: string;
  label: string;
  required: boolean;
}

interface ColumnOption {
  index: number;
  name: string;
  sample: string;
}

/**
 * Column Mapper Component
 * 
 * Maps CSV columns to target vehicle fields with:
 * - Exclusive selection (one CSV column per field)
 * - Required field indicators
 * - "Do not import" option
 * - Preview of transformed data
 */
@Component({
  selector: 'app-column-mapper',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatFormFieldModule,
    MatSelectModule,
    MatTableModule,
    MatIconModule,
    MatProgressSpinnerModule
  ],
  templateUrl: './column-mapper.component.html',
  styleUrl: './column-mapper.component.scss'
})
export class ColumnMapperComponent implements OnInit {
  @Input() file!: File;
  @Input() skipLines = 4;
  @Output() mappingChange = new EventEmitter<Map<string, string>>();
  
  // Target fields (CLEF vehicle fields)
  targetFields: TargetField[] = [
    { key: 'immat', label: 'Immatriculation', required: true },
    { key: 'dt_ul', label: 'DT / UL', required: true },
    { key: 'indicatif', label: 'Indicatif', required: true },
    { key: 'marque', label: 'Marque', required: false },
    { key: 'modele', label: 'Modèle', required: false },
    { key: 'type', label: 'Type', required: false },
    { key: 'operationnel_mecanique', label: 'Statut opérationnel', required: false },
    { key: 'raison_indispo', label: 'Raison indisponibilité', required: false },
    { key: 'prochain_controle_technique', label: 'Prochain CT', required: false },
    { key: 'prochain_controle_pollution', label: 'Prochain contrôle pollution', required: false },
    { key: 'date_mec', label: 'Date de MEC', required: false },
    { key: 'nom_synthetique', label: 'Nom synthétique', required: false },
    { key: 'carte_grise', label: 'Carte grise', required: false },
    { key: 'nb_places', label: 'Nombre de places', required: false },
    { key: 'commentaires', label: 'Commentaires', required: false },
    { key: 'lieu_stationnement', label: 'Lieu de stationnement', required: false },
    { key: 'instructions_recuperation', label: 'Instructions récupération', required: false },
    { key: 'assurance_2026', label: 'Assurance 2026', required: false },
    { key: 'numero_serie_baus', label: 'N° Série BAUS', required: false }
  ];
  
  // CSV columns detected from file
  csvColumns = signal<ColumnOption[]>([]);
  
  // Current mapping: targetField -> csvColumnIndex
  mapping = signal<Map<string, number>>(new Map());
  
  // Loading state
  loading = signal(false);
  
  // Preview data
  previewData = signal<any[]>([]);
  
  // Computed: check if all required fields are mapped
  isValid = computed(() => {
    const map = this.mapping();
    return this.targetFields
      .filter(f => f.required)
      .every(f => map.has(f.key) && map.get(f.key)! >= 0);
  });
  
  ngOnInit(): void {
    this.loadCsvColumns();
  }
  
  /**
   * Load CSV columns from file
   */
  private async loadCsvColumns(): Promise<void> {
    if (!this.file) return;
    
    this.loading.set(true);
    try {
      const text = await this.file.text();
      const lines = text.split('\n').filter(l => l.trim());
      
      // Get header line (after skipping configured lines)
      const headerLine = lines[this.skipLines];
      if (!headerLine) {
        console.error('No header line found');
        return;
      }
      
      const headers = headerLine.split(',').map(h => h.trim());
      
      // Get first data line for sample
      const dataLine = lines[this.skipLines + 1];
      const samples = dataLine ? dataLine.split(',').map(s => s.trim()) : [];
      
      // Create column options
      const columns: ColumnOption[] = headers.map((name, index) => ({
        index,
        name,
        sample: samples[index] || ''
      }));
      
      this.csvColumns.set(columns);
      
      // Auto-suggest mapping based on column names
      this.autoSuggestMapping(headers);
      
    } catch (error) {
      console.error('Error loading CSV columns:', error);
    } finally {
      this.loading.set(false);
    }
  }
  
  /**
   * Auto-suggest mapping based on column names
   */
  private autoSuggestMapping(headers: string[]): void {
    const newMapping = new Map<string, number>();
    
    // Simple matching logic
    const normalizeHeader = (h: string) => h.toLowerCase().replace(/[^a-z0-9]/g, '');
    
    this.targetFields.forEach(field => {
      const fieldNorm = normalizeHeader(field.label);
      const matchIndex = headers.findIndex(h => 
        normalizeHeader(h).includes(fieldNorm) || 
        fieldNorm.includes(normalizeHeader(h))
      );
      
      if (matchIndex >= 0) {
        newMapping.set(field.key, matchIndex);
      }
    });
    
    this.mapping.set(newMapping);
    this.emitMapping();
  }
  
  /**
   * Handle mapping change for a field
   */
  onMappingChange(fieldKey: string, columnIndex: number): void {
    const newMapping = new Map(this.mapping());
    
    if (columnIndex === -1) {
      // "Do not import" selected
      newMapping.delete(fieldKey);
    } else {
      newMapping.set(fieldKey, columnIndex);
    }
    
    this.mapping.set(newMapping);
    this.emitMapping();
  }
  
  /**
   * Emit mapping change
   */
  private emitMapping(): void {
    // Convert Map<string, number> to Map<string, string> for parent
    const stringMap = new Map<string, string>();
    this.mapping().forEach((colIndex, fieldKey) => {
      stringMap.set(fieldKey, colIndex.toString());
    });
    this.mappingChange.emit(stringMap);
  }
  
  /**
   * Check if a column is already used
   */
  isColumnUsed(columnIndex: number, currentField: string): boolean {
    const map = this.mapping();
    for (const [field, colIdx] of map.entries()) {
      if (field !== currentField && colIdx === columnIndex) {
        return true;
      }
    }
    return false;
  }
}

