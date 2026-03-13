import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

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
 * Import error detail (matches backend ImportError)
 */
export interface ImportError {
  line_number: number;
  reason: string;
  values?: string[];
}

/**
 * Import result (matches backend ImportResult)
 */
export interface ImportResult {
  total_lines: number;
  ignored_lines: number;
  created: number;
  updated: number;
  errors: ImportError[];
}

/**
 * Column info from preview
 */
export interface ColumnInfo {
  index: number;
  header: string | null;
  sample_values: string[];
  suggested_field: string | null;
}

/**
 * Preview row
 */
export interface PreviewRow {
  line_number: number;
  values: string[];
}

/**
 * CSV preview response (matches backend PreviewResponse)
 */
export interface CsvPreviewResponse {
  total_lines: number;
  skip_lines: number;
  columns: ColumnInfo[];
  preview_rows: PreviewRow[];
  suggested_mappings: ColumnMapping[];
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
  private readonly apiUrl = environment.apiUrl;
  
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
      `${this.apiUrl}/api/${dt}/import/vehicles/preview`,
      formData,
      { withCredentials: true }
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
    formData.append('config_json', JSON.stringify(config));
    
    // TODO: Replace with actual DT from user context
    const dt = 'DT75';
    
    return this.http.post<ImportResult>(
      `${this.apiUrl}/api/${dt}/import/vehicles`,
      formData,
      { withCredentials: true }
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

