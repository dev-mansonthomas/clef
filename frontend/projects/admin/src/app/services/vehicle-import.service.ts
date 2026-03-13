import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

/**
 * Column mapping for CSV import
 */
export interface ColumnMapping {
  csv_column: number;  // Index of CSV column
  target_field: string;  // Target Valkey field or "skip"
}

/**
 * Import configuration
 */
export interface ImportConfig {
  skip_lines: number;
  mappings: ColumnMapping[];
}

/**
 * Import error detail
 */
export interface ImportError {
  ligne: number;
  raison: string;
}

/**
 * Import result
 */
export interface ImportResult {
  total_lignes: number;
  lignes_ignorees: number;
  vehicules_crees: number;
  vehicules_maj: number;
  erreurs: ImportError[];
}

/**
 * CSV preview response
 */
export interface CsvPreviewResponse {
  columns: string[];
  preview_data: string[][];
  suggested_mapping: Record<string, number>;
}

/**
 * Vehicle Import Service
 * 
 * Handles CSV import operations for vehicles
 */
@Injectable({
  providedIn: 'root'
})
export class VehicleImportService {
  private readonly apiUrl = '/api';
  
  constructor(private http: HttpClient) {}
  
  /**
   * Upload CSV and get preview with column detection
   * 
   * @param file CSV file to upload
   * @param skipLines Number of lines to skip
   * @returns Preview data with detected columns and suggested mapping
   */
  previewCsv(file: File, skipLines: number = 4): Observable<CsvPreviewResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('skip_lines', skipLines.toString());
    
    // TODO: Replace with actual DT from user context
    const dt = 'DT75';
    
    return this.http.post<CsvPreviewResponse>(
      `${this.apiUrl}/${dt}/import/vehicles/preview`,
      formData
    );
  }
  
  /**
   * Import vehicles from CSV with provided mapping
   * 
   * @param file CSV file to import
   * @param config Import configuration with mapping
   * @returns Import result with statistics and errors
   */
  importVehicles(file: File, config: ImportConfig): Observable<ImportResult> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('config', JSON.stringify(config));
    
    // TODO: Replace with actual DT from user context
    const dt = 'DT75';
    
    return this.http.post<ImportResult>(
      `${this.apiUrl}/${dt}/import/vehicles`,
      formData
    );
  }
  
  /**
   * Convert mapping from Map to ColumnMapping array
   * 
   * @param mapping Map of target field to CSV column index
   * @returns Array of ColumnMapping objects
   */
  convertMapping(mapping: Map<string, string>): ColumnMapping[] {
    const mappings: ColumnMapping[] = [];
    
    mapping.forEach((columnIndex, targetField) => {
      mappings.push({
        csv_column: parseInt(columnIndex, 10),
        target_field: targetField
      });
    });
    
    return mappings;
  }
}

