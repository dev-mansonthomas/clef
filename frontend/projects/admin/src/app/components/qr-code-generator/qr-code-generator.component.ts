import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatIconModule } from '@angular/material/icon';
import { QRCodeComponent } from 'angularx-qrcode';
import { VehicleService } from '../../services/vehicle.service';
import { QrCodeService } from '../../services/qr-code.service';
import { Vehicle } from '../../models/vehicle.model';

interface VehicleQrCode {
  vehicle: Vehicle;
  qrCodeUrl: string;
}

/**
 * Component for generating and printing QR codes for vehicles
 */
@Component({
  selector: 'app-qr-code-generator',
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatCardModule,
    MatProgressSpinnerModule,
    MatIconModule,
    QRCodeComponent
  ],
  templateUrl: './qr-code-generator.component.html',
  styleUrls: ['./qr-code-generator.component.scss']
})
export class QrCodeGeneratorComponent implements OnInit {
  protected readonly loading = signal(false);
  protected readonly vehicleQrCodes = signal<VehicleQrCode[]>([]);
  protected readonly error = signal<string | null>(null);

  constructor(
    private vehicleService: VehicleService,
    private qrCodeService: QrCodeService
  ) {}

  /**
   * Get instruction message based on vehicle's suivi_mode
   */
  protected getInstructionMessage(vehicle: Vehicle): string {
    const suiviMode = vehicle.suivi_mode || 'prise';

    switch (suiviMode) {
      case 'prise':
        return 'À la prise du véhicule, veuillez remplir le formulaire CLEF';
      case 'retour':
        return 'Au retour du véhicule, veuillez remplir le formulaire CLEF';
      case 'prise_et_retour':
        return 'À la prise et au retour du véhicule, veuillez remplir le formulaire CLEF';
      default:
        return 'À la prise du véhicule, veuillez remplir le formulaire CLEF';
    }
  }

  ngOnInit(): void {
    this.loadVehicles();
  }

  /**
   * Load all vehicles and generate QR codes
   */
  private loadVehicles(): void {
    this.loading.set(true);
    this.error.set(null);

    this.vehicleService.getVehicles().subscribe({
      next: (response) => {
        // Sort vehicles by DT/UL then by Indicatif (same as vehicle list)
        const sortedVehicles = response.vehicles.sort((a, b) => {
          // Primary sort by dt_ul
          const dtCompare = (a.dt_ul || '').localeCompare(b.dt_ul || '');
          if (dtCompare !== 0) return dtCompare;

          // Secondary sort by indicatif
          return (a.indicatif || '').localeCompare(b.indicatif || '');
        });

        const qrCodes: VehicleQrCode[] = [];

        sortedVehicles.forEach(vehicle => {
          this.qrCodeService.generateQrCodeUrl(vehicle.nom_synthetique).subscribe({
            next: (url) => {
              qrCodes.push({
                vehicle,
                qrCodeUrl: url
              });

              // Update signal when all QR codes are generated
              if (qrCodes.length === sortedVehicles.length) {
                this.vehicleQrCodes.set(qrCodes);
                this.loading.set(false);
              }
            },
            error: (err) => {
              console.error('Error generating QR code:', err);
              this.error.set('Erreur lors de la génération des QR codes');
              this.loading.set(false);
            }
          });
        });

        // Handle empty vehicle list
        if (sortedVehicles.length === 0) {
          this.loading.set(false);
        }
      },
      error: (err) => {
        console.error('Error loading vehicles:', err);
        this.error.set('Erreur lors du chargement des véhicules');
        this.loading.set(false);
      }
    });
  }

  /**
   * Print all QR codes
   */
  protected printQrCodes(): void {
    window.print();
  }

  /**
   * Print a single QR code
   */
  protected printSingleQrCode(vehicleQrCode: VehicleQrCode): void {
    // Store current QR codes
    const allQrCodes = this.vehicleQrCodes();
    
    // Temporarily show only the selected QR code
    this.vehicleQrCodes.set([vehicleQrCode]);
    
    // Print
    setTimeout(() => {
      window.print();
      
      // Restore all QR codes after print dialog
      setTimeout(() => {
        this.vehicleQrCodes.set(allQrCodes);
      }, 100);
    }, 100);
  }

  /**
   * Reload vehicles and regenerate QR codes
   */
  protected reload(): void {
    this.loadVehicles();
  }
}

