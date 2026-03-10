import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';

/**
 * Service for QR code generation and encoding
 */
@Injectable({
  providedIn: 'root'
})
export class QrCodeService {
  private readonly configUrl = '/api/config';

  constructor(private http: HttpClient) {}

  /**
   * Generate QR code URL for a vehicle
   * The QR code will encode a URL to the form application
   * Format: https://{DOMAIN}/vehicle/{encoded_id}
   * 
   * The encoded_id is generated on the backend using nom_synthetique + SALT
   * 
   * @param nomSynthetique - Vehicle's synthetic name
   * @returns Observable with the form URL to encode in QR
   */
  generateQrCodeUrl(nomSynthetique: string): Observable<string> {
    // Get the domain from environment or config
    const domain = this.getDomain();
    
    // For now, we'll use the nom_synthetique directly
    // In production, this should be hashed with SALT on the backend
    // The form app will decode it using the same SALT
    const encodedId = this.encodeVehicleId(nomSynthetique);
    
    return new Observable<string>(observer => {
      observer.next(`https://${domain}/vehicle/${encodedId}`);
      observer.complete();
    });
  }

  /**
   * Get the domain from environment
   * This should match the DOMAIN env variable
   */
  private getDomain(): string {
    // In production, this would come from environment configuration
    // For now, using a placeholder
    return window.location.hostname.replace('admin.', '');
  }

  /**
   * Encode vehicle ID (nom_synthetique)
   * In production, this should call the backend to hash with SALT
   * For now, using base64 encoding as a placeholder
   */
  private encodeVehicleId(nomSynthetique: string): string {
    // Simple base64 encoding for now
    // TODO: Replace with backend API call that uses SALT
    return btoa(nomSynthetique);
  }

  /**
   * Get QR code configuration from backend
   * This would include SALT and other QR-related settings
   */
  getQrConfig(): Observable<any> {
    return this.http.get(`${this.configUrl}`);
  }
}

