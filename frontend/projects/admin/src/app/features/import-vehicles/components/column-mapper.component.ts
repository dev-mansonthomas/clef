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
    { id: 'indicatif', label: 'Indicatif', required: false },
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
    { id: 'num_baus', label: 'N° de série constructeur', required: false }
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
      // skipLines = 5 means we skip lines 0-4 (indices 0-4)
      // The CSV headers are at index skipLines (line skipLines+1)
      // Data starts at index skipLines+1 (line skipLines+2)
      // Example: skipLines=5 → headers at index 5 (line 6), data starts at index 6 (line 7)
      if (allRows.length <= this.skipLines + 1) {
        console.error('Not enough lines in CSV file');
        return;
      }

      // Headers are at skipLines index, data is at skipLines+1 index
      const headerRowIndex = this.skipLines;      // skipLines=5 → index 5 (line 6)
      const dataRowIndex = this.skipLines + 1;    // skipLines=5 → index 6 (line 7)

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

    // DT75 Standard Format: If we have exactly 19 columns, apply default DT75 mapping
    if (headers.length === 19) {
      // Standard DT75 CSV mapping (columns A-S, indices 0-18)
      const dt75Mapping: Record<number, string> = {
        0: 'dt_ul',                    // A: DT 75 / UL
        1: 'immat',                    // B: Immatriculation
        2: 'indicatif',                // C: Indicatif
        3: 'statut',                   // D: Opérationnel mécanique
        4: 'raison_indispo',           // E: Raison indispo
        5: 'prochain_ct',              // F: Prochain contrôle technique
        6: 'prochain_pollution',       // G: Prochain contrôle pollution
        7: 'marque',                   // H: Marque
        8: 'modele',                   // I: Modèle
        9: 'type',                     // J: Type
        10: 'date_mec',                // K: Date MEC
        11: 'nom_synthetique',         // L: Nom synthétique
        12: 'carte_grise',             // M: Carte grise
        13: 'nb_places',               // N: # de Place
        14: 'commentaires',            // O: Commentaires
        15: 'lieu_stationnement',      // P: Lieu de stationnement
        16: 'instructions',            // Q: Instructions pour récupérer
        17: 'assurance',               // R: Assurance
        18: 'num_baus'                 // S: N° de série
      };

      // Apply DT75 default mapping
      Object.entries(dt75Mapping).forEach(([csvIndex, clefFieldId]) => {
        newMapping.set(Number(csvIndex), clefFieldId);
      });

      this.mapping.set(newMapping);
      this.emitMapping();
      return;
    }

    // Normalize string for comparison
    const normalize = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, '');

    // Define explicit mappings for common CSV column names
    const explicitMappings: Record<string, string> = {
      // DT/UL variations
      'dt75ul': 'dt_ul',
      'dt75': 'dt_ul',
      'dtul': 'dt_ul',
      'dt': 'dt_ul',
      'ul': 'dt_ul',
      // Immatriculation variations
      'immat': 'immat',
      'immatriculation': 'immat',
      // Indicatif variations
      'indicatif': 'indicatif',
      // Statut variations
      'operationnelmecanique': 'statut',
      'operationnel': 'statut',
      'statut': 'statut',
      'disponibilite': 'statut',
      'dispo': 'statut',
      // Marque variations
      'marque': 'marque',
      // Modèle variations (accent-insensitive via normalize)
      'modele': 'modele',
      'model': 'modele',
      // Type
      'type': 'type',
      // Raison indispo variations
      'raisonindispo': 'raison_indispo',
      'raison': 'raison_indispo',
      // Contrôle technique variations
      'prochaincontroletechnique': 'prochain_ct',
      'prochainct': 'prochain_ct',
      'controletechnique': 'prochain_ct',
      'ct': 'prochain_ct',
      // Contrôle pollution variations
      'prochaincontrolepollution': 'prochain_pollution',
      'prochainpollution': 'prochain_pollution',
      'controlepollution': 'prochain_pollution',
      'pollution': 'prochain_pollution',
      // Date MEC
      'datemec': 'date_mec',
      'mec': 'date_mec',
      'miseencirculation': 'date_mec',
      // Nom synthétique variations (handles both "Synthétique" and "Syntéthique" via normalize)
      'nomsynthetique': 'nom_synthetique',
      'nom': 'nom_synthetique',
      // Carte grise variations
      'cartegrise': 'carte_grise',
      // Nombre de places variations
      'deplace': 'nb_places',  // "# de Place"
      'nbplaces': 'nb_places',
      'nombreplaces': 'nb_places',
      'nombredeplace': 'nb_places',
      'nombredeplacess': 'nb_places',
      'places': 'nb_places',
      // Commentaires variations
      'commentaires': 'commentaires',
      'commentaire': 'commentaires',
      'comment': 'commentaires',
      // Lieu de stationnement variations
      'lieustationnement': 'lieu_stationnement',
      'lieudestationnement': 'lieu_stationnement',
      'lieu': 'lieu_stationnement',
      'stationnement': 'lieu_stationnement',
      // Instructions variations
      'instructions': 'instructions',
      'instruction': 'instructions',
      'instructionspourrecuperer': 'instructions',
      'instructionspourrecuprer': 'instructions',  // Common typo
      // Assurance
      'assurance': 'assurance',
      // N° de série constructeur / BAUS variations
      'nserie': 'num_baus',
      'ndeserie': 'num_baus',
      'numeroserie': 'num_baus',
      'numerodeserie': 'num_baus',
      'numbaus': 'num_baus',
      'numerobaus': 'num_baus',
      'baus': 'num_baus'
    };

    // Try to match each CSV column to a CLEF field
    headers.forEach((header, csvIndex) => {
      const headerNorm = normalize(header);

      // First, try explicit mappings
      let matchedFieldId: string | undefined = explicitMappings[headerNorm];

      // If no explicit match, try fuzzy matching with CLEF field labels
      if (!matchedFieldId) {
        const match = this.CLEF_FIELDS.find(field => {
          const fieldNorm = normalize(field.label);
          // Check if header contains field name or vice versa
          return headerNorm.includes(fieldNorm) || fieldNorm.includes(headerNorm);
        });
        matchedFieldId = match?.id;
      }

      // Only map if we found a match and this CLEF field hasn't been used yet
      if (matchedFieldId && !Array.from(newMapping.values()).includes(matchedFieldId)) {
        newMapping.set(csvIndex, matchedFieldId);
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

