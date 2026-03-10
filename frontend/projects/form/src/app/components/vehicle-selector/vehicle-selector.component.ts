import { Component, OnInit, OnDestroy, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, ActivatedRoute } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatSelectModule } from '@angular/material/select';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatIconModule } from '@angular/material/icon';
import { FormsModule } from '@angular/forms';
import { Html5Qrcode } from 'html5-qrcode';
import { VehicleService } from '../../services/vehicle.service';
import { Vehicle } from '../../models/vehicle.model';

/**
 * Vehicle selector component with QR scanning and manual selection
 */
@Component({
  selector: 'app-vehicle-selector',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatCardModule,
    MatSelectModule,
    MatFormFieldModule,
    MatProgressSpinnerModule,
    MatIconModule
  ],
  templateUrl: './vehicle-selector.component.html',
  styleUrls: ['./vehicle-selector.component.scss']
})
export class VehicleSelectorComponent implements OnInit, OnDestroy {
  protected readonly loading = signal(false);
  protected readonly scanning = signal(false);
  protected readonly vehicles = signal<Vehicle[]>([]);
  protected readonly selectedVehicle = signal<string | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly cameraError = signal<string | null>(null);

  private html5QrCode: Html5Qrcode | null = null;
  private readonly qrCodeRegionId = 'qr-reader';

  constructor(
    private vehicleService: VehicleService,
    private router: Router,
    private route: ActivatedRoute
  ) {}

  ngOnInit(): void {
    this.loadVehicles();
    this.checkForEncodedId();
  }

  /**
   * Check if we arrived via QR code scan (URL contains encodedId)
   */
  private checkForEncodedId(): void {
    const encodedId = this.route.snapshot.paramMap.get('encodedId');
    if (encodedId) {
      try {
        // Decode the base64 encoded nom_synthetique
        const nomSynthetique = atob(encodedId);
        this.navigateToForm(nomSynthetique);
      } catch (error) {
        console.error('Error decoding vehicle ID:', error);
        this.error.set('QR code invalide. Veuillez sélectionner un véhicule manuellement.');
      }
    }
  }

  ngOnDestroy(): void {
    this.stopScanning();
  }

  /**
   * Load all vehicles for manual selection
   */
  private loadVehicles(): void {
    this.loading.set(true);
    this.error.set(null);

    this.vehicleService.getVehicles().subscribe({
      next: (response) => {
        this.vehicles.set(response.vehicles);
        this.loading.set(false);
      },
      error: (err) => {
        console.error('Error loading vehicles:', err);
        this.error.set('Erreur lors du chargement des véhicules');
        this.loading.set(false);
      }
    });
  }

  /**
   * Start QR code scanning
   */
  protected async startScanning(): Promise<void> {
    this.scanning.set(true);
    this.cameraError.set(null);
    this.error.set(null);

    try {
      this.html5QrCode = new Html5Qrcode(this.qrCodeRegionId);

      await this.html5QrCode.start(
        { facingMode: 'environment' }, // Use back camera on mobile
        {
          fps: 10,
          qrbox: { width: 250, height: 250 }
        },
        this.onScanSuccess.bind(this),
        this.onScanError.bind(this)
      );
    } catch (err: any) {
      console.error('Error starting QR scanner:', err);
      this.cameraError.set(
        'Impossible d\'accéder à la caméra. Veuillez autoriser l\'accès à la caméra ou utiliser la sélection manuelle.'
      );
      this.scanning.set(false);
    }
  }

  /**
   * Stop QR code scanning
   */
  protected async stopScanning(): Promise<void> {
    if (this.html5QrCode && this.scanning()) {
      try {
        await this.html5QrCode.stop();
        this.html5QrCode.clear();
        this.html5QrCode = null;
      } catch (err) {
        console.error('Error stopping QR scanner:', err);
      }
    }
    this.scanning.set(false);
  }

  /**
   * Handle successful QR code scan
   */
  private onScanSuccess(decodedText: string): void {
    console.log('QR Code scanned:', decodedText);

    // Decode the QR code to get nom_synthetique
    const nomSynthetique = this.vehicleService.decodeQrCode(decodedText);

    if (nomSynthetique) {
      this.stopScanning();
      this.navigateToForm(nomSynthetique);
    } else {
      this.error.set('QR code invalide. Veuillez réessayer ou utiliser la sélection manuelle.');
    }
  }

  /**
   * Handle QR code scan errors (silent - only log)
   */
  private onScanError(errorMessage: string): void {
    // Don't show errors for every failed scan attempt
    // Only log to console for debugging
    // console.log('QR scan error:', errorMessage);
  }

  /**
   * Handle manual vehicle selection
   */
  protected onVehicleSelected(): void {
    const nomSynthetique = this.selectedVehicle();
    if (nomSynthetique) {
      this.navigateToForm(nomSynthetique);
    }
  }

  /**
   * Navigate to the appropriate form (prise or retour)
   * For now, defaulting to 'prise' - context detection can be added later
   */
  private navigateToForm(nomSynthetique: string): void {
    // TODO: Add context detection to determine if it's prise or retour
    // For MVP, defaulting to prise
    this.router.navigate(['/prise', nomSynthetique]);
  }
}

