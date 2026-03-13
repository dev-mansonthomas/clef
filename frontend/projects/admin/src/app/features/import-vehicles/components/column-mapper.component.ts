import { Component, Input, Output, EventEmitter, OnChanges, SimpleChanges, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatTableModule } from '@angular/material/table';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import Papa from 'papaparse';

interface ClefField {
  id: string;
  label: string;
  required: boolean;
}

interface CsvColumn {
  index: number;
  name: string;
  exampleValue: string;
}

/**
 * Column Mapper Component
 *
 * REVERSED MAPPING LOGIC:
 * - Column 1: CSV columns in file order (e.g., "Column A: DT 75 / UL")
 * - Column 2: Dropdown with CLEF fields (Immatriculation, DT/UL, etc.)
 * - Exclusive selection: When a CLEF field is selected, it disappears from other dropdowns
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
export class ColumnMapperComponent implements OnChanges {
  @Input() file!: File;
  @Input() skipLines = 4;
  @Output() mappingChange = new EventEmitter<Map<string, string>>();

  // CLEF fields (target fields for mapping)
  readonly CLEF_FIELDS: ClefField[] = [
    { id: 'immat', label: 'Immatriculation *', required: true },
    { id: 'dt_ul', label: 'DT / UL *', required: true },
    { id: 'indicatif', label: 'Indicatif *', required: true },
    { id: 'marque', label: 'Marque', required: false },
    { id: 'modele', label: 'Modèle', required: false },
    { id: 'type', label: 'Type', required: false },
    { id: 'statut', label: 'Statut (Dispo/Indispo)', required: false },
    { id: 'raison_indispo', label: 'Raison indispo', required: false },
    { id: 'prochain_ct', label: 'Prochain CT', required: false },
    { id: 'prochain_pollution', label: 'Prochain contrôle pollution', required: false },
    { id: 'date_mec', label: 'Date MEC', required: false },
    { id: 'nom_synthetique', label: 'Nom synthétique', required: false },
    { id: 'carte_grise', label: 'Carte grise', required: false },
    { id: 'nb_places', label: 'Nombre de places', required: false },
    { id: 'commentaires', label: 'Commentaires', required: false },
    { id: 'lieu_stationnement', label: 'Lieu de stationnement', required: false },
    { id: 'instructions', label: 'Instructions', required: false },
    { id: 'assurance', label: 'Assurance', required: false },
    { id: 'num_baus', label: 'Numéro BAUS', required: false }
  ];

  // CSV columns detected from file (in file order)
  csvColumns = signal<CsvColumn[]>([]);

  // Current mapping: csvColumnIndex -> clefFieldId
  // Example: { 0: 'dt_ul', 1: 'immat', 2: 'indicatif', ... }
  mapping = signal<Map<number, string>>(new Map());

  // Loading state
  loading = signal(false);

  // Computed: check if all required fields are mapped
  isValid = computed(() => {
    const map = this.mapping();
    const mappedFields = new Set(Array.from(map.values()));
    return this.CLEF_FIELDS
      .filter(f => f.required)
      .every(f => mappedFields.has(f.id));
  });

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['file'] && this.file) {
      this.loadCsvColumns();
    }
    if (changes['skipLines'] && this.file) {
      this.loadCsvColumns();
    }
  }

  /**
   * Load CSV columns from file
   */
  private async loadCsvColumns(): Promise<void> {
    if (!this.file) return;

    this.loading.set(true);
    try {
      const text = await this.file.text();

      // Parse CSV with PapaParse
      const parseResult = Papa.parse(text, {
        skipEmptyLines: true,
        header: false
      });

      if (parseResult.errors.length > 0) {
        console.warn('CSV parsing warnings:', parseResult.errors);
      }

      const allRows = parseResult.data as string[][];

      // Get header line (after skipping configured lines)
      // skipLines = 6 means we skip lines 1-6 for import
      // The CSV headers are at the line BEFORE the first data line
      // Example: skipLines=6 → headers at line 5 (index 4), data starts at line 6 (index 5)
      if (allRows.length <= this.skipLines) {
        console.error('Not enough lines in CSV file');
        return;
      }

      // Headers are 2 lines before skipLines, data is 1 line before
      const headerRowIndex = this.skipLines >= 2 ? this.skipLines - 2 : 0;  // Line 5 = index 4
      const dataRowIndex = this.skipLines >= 1 ? this.skipLines - 1 : 0;    // Line 6 = index 5

      const headerRow = allRows[headerRowIndex];
      const dataRow = allRows[dataRowIndex] || [];

      // Create CSV columns in file order
      const columns: CsvColumn[] = headerRow.map((name, index) => ({
        index,
        name: name || `Column ${index + 1}`,
        exampleValue: dataRow[index] || ''
      }));

      this.csvColumns.set(columns);

      // Auto-suggest mapping based on column names
      this.autoSuggestMapping(headerRow);

    } catch (error) {
      console.error('Error loading CSV columns:', error);
    } finally {
      this.loading.set(false);
    }
  }

  /**
   * Auto-suggest mapping based on column names
   * Tries to intelligently match CSV column names to CLEF fields
   */
  private autoSuggestMapping(headers: string[]): void {
    const newMapping = new Map<number, string>();

    // Normalize string for comparison
    const normalize = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, '');

    // Try to match each CSV column to a CLEF field
    headers.forEach((header, csvIndex) => {
      const headerNorm = normalize(header);

      // Find best matching CLEF field
      const match = this.CLEF_FIELDS.find(field => {
        const fieldNorm = normalize(field.label);
        // Check if header contains field name or vice versa
        return headerNorm.includes(fieldNorm) || fieldNorm.includes(headerNorm);
      });

      if (match && !Array.from(newMapping.values()).includes(match.id)) {
        // Only map if this CLEF field hasn't been used yet
        newMapping.set(csvIndex, match.id);
      }
    });

    this.mapping.set(newMapping);
    this.emitMapping();
  }

  /**
   * Handle mapping change for a CSV column
   */
  onMappingChange(csvColumnIndex: number, clefFieldId: string): void {
    const newMapping = new Map(this.mapping());

    if (clefFieldId === 'skip') {
      // "Do not import" selected
      newMapping.delete(csvColumnIndex);
    } else {
      newMapping.set(csvColumnIndex, clefFieldId);
    }

    this.mapping.set(newMapping);
    this.emitMapping();
  }

  /**
   * Get the currently mapped CLEF field for a CSV column
   */
  getMapping(csvColumnIndex: number): string {
    return this.mapping().get(csvColumnIndex) || 'skip';
  }

  /**
   * Get available CLEF fields for a CSV column (excluding already selected ones)
   */
  getAvailableFields(csvColumnIndex: number): ClefField[] {
    const currentMapping = this.getMapping(csvColumnIndex);
    const selectedFieldIds = Array.from(this.mapping().values())
      .filter(fieldId => fieldId !== currentMapping);

    return this.CLEF_FIELDS.filter(f => !selectedFieldIds.includes(f.id));
  }

  /**
   * Get column letter (A, B, C, ...)
   */
  getColumnLetter(index: number): string {
    return String.fromCharCode(65 + index); // 65 = 'A'
  }

  /**
   * Get missing required fields
   */
  getMissingRequiredFields(): string[] {
    const mappedFields = new Set(Array.from(this.mapping().values()));
    return this.CLEF_FIELDS
      .filter(f => f.required && !mappedFields.has(f.id))
      .map(f => f.label);
  }

  /**
   * Check if all required fields are mapped
   */
  allRequiredFieldsMapped(): boolean {
    return this.isValid();
  }

  /**
   * Emit mapping change to parent component
   */
  private emitMapping(): void {
    // Convert Map<number, string> to Map<string, string> for parent
    // Parent expects: { 'immat': '1', 'dt_ul': '0', ... }
    const stringMap = new Map<string, string>();
    this.mapping().forEach((clefFieldId, csvIndex) => {
      stringMap.set(clefFieldId, csvIndex.toString());
    });
    this.mappingChange.emit(stringMap);
  }
}

