import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';

import { QrCodeGeneratorComponent } from './qr-code-generator.component';
import { VehicleService } from '../../services/vehicle.service';
import { QrCodeService } from '../../services/qr-code.service';

/**
 * Ces specs étaient écrites en Jasmine (`jasmine.createSpyObj`, `spyOn`) alors que
 * le projet exécute Vitest via `@angular/build:unit-test` : elles ne compilaient
 * pas, ce qui privait tout le frontend de filet unitaire (docs/TODO.md M4).
 */
describe('QrCodeGeneratorComponent', () => {
  let component: QrCodeGeneratorComponent;
  let fixture: ComponentFixture<QrCodeGeneratorComponent>;
  let vehicleService: { getVehicles: ReturnType<typeof vi.fn> };
  let qrCodeService: { generateQrCodeUrl: ReturnType<typeof vi.fn> };

  /** Véhicule complet : le composant trie sur dt_ul puis indicatif. */
  const mockVehicle = {
    dt_ul: 'UL Test',
    immat: 'AB-123-CD',
    indicatif: 'TEST-01',
    operationnel_mecanique: 'Dispo' as const,
    raison_indispo: '',
    prochain_controle_technique: '2026-12-31',
    prochain_controle_pollution: '2026-12-31',
    marque: 'Renault',
    modele: 'Master',
    type: 'VSAV',
    date_mec: '2020-01-01',
    nom_synthetique: 'VSAV-TEST-01',
    carte_grise: 'CG123',
    nb_places: '3',
    commentaires: '',
    lieu_stationnement: 'Garage',
    instructions_recuperation: '',
    assurance_2026: '',
    numero_serie_baus: '',
    status_ct: { value: '2026-12-31', color: 'green' as const },
    status_pollution: { value: '2026-12-31', color: 'green' as const },
    status_disponibilite: { value: 'Dispo', color: 'green' as const },
  };

  beforeEach(async () => {
    vehicleService = { getVehicles: vi.fn() };
    qrCodeService = { generateQrCodeUrl: vi.fn() };

    // Défaut sûr : `ngOnInit` appelle getVehicles dès le premier detectChanges.
    vehicleService.getVehicles.mockReturnValue(of({ count: 0, vehicles: [] }));
    qrCodeService.generateQrCodeUrl.mockReturnValue(
      of('https://example.com/vehicle/test'),
    );

    await TestBed.configureTestingModule({
      imports: [QrCodeGeneratorComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: VehicleService, useValue: vehicleService },
        { provide: QrCodeService, useValue: qrCodeService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(QrCodeGeneratorComponent);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should load vehicles on init', () => {
    vehicleService.getVehicles.mockReturnValue(
      of({ count: 1, vehicles: [mockVehicle] }),
    );

    fixture.detectChanges();

    expect(vehicleService.getVehicles).toHaveBeenCalled();
    // Le QR code est bien demandé pour le véhicule chargé.
    expect(qrCodeService.generateQrCodeUrl).toHaveBeenCalledWith('VSAV-TEST-01');
  });

  it('should handle error when loading vehicles', () => {
    vehicleService.getVehicles.mockReturnValue(
      throwError(() => new Error('Test error')),
    );

    fixture.detectChanges();

    // `error` est `protected` : accès par indexation plutôt qu'élargir la
    // visibilité du composant pour les besoins du test.
    expect(component['error']()).toBeTruthy();
  });

  it('should call window.print when printQrCodes is called', () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => {});

    component['printQrCodes']();

    expect(print).toHaveBeenCalled();
  });
});
