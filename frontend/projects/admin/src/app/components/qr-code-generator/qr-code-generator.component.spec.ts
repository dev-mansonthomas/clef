import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { QrCodeGeneratorComponent } from './qr-code-generator.component';
import { VehicleService } from '../../services/vehicle.service';
import { QrCodeService } from '../../services/qr-code.service';
import { of, throwError } from 'rxjs';

describe('QrCodeGeneratorComponent', () => {
  let component: QrCodeGeneratorComponent;
  let fixture: ComponentFixture<QrCodeGeneratorComponent>;
  let vehicleService: jasmine.SpyObj<VehicleService>;
  let qrCodeService: jasmine.SpyObj<QrCodeService>;

  beforeEach(async () => {
    const vehicleServiceSpy = jasmine.createSpyObj('VehicleService', ['getVehicles']);
    const qrCodeServiceSpy = jasmine.createSpyObj('QrCodeService', ['generateQrCodeUrl']);

    await TestBed.configureTestingModule({
      imports: [QrCodeGeneratorComponent, HttpClientTestingModule],
      providers: [
        { provide: VehicleService, useValue: vehicleServiceSpy },
        { provide: QrCodeService, useValue: qrCodeServiceSpy }
      ]
    }).compileComponents();

    vehicleService = TestBed.inject(VehicleService) as jasmine.SpyObj<VehicleService>;
    qrCodeService = TestBed.inject(QrCodeService) as jasmine.SpyObj<QrCodeService>;

    fixture = TestBed.createComponent(QrCodeGeneratorComponent);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should load vehicles on init', () => {
    const mockResponse = {
      count: 1,
      vehicles: [{
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
        status_disponibilite: { value: 'Dispo', color: 'green' as const }
      }]
    };

    vehicleService.getVehicles.and.returnValue(of(mockResponse));
    qrCodeService.generateQrCodeUrl.and.returnValue(of('https://example.com/vehicle/test'));

    fixture.detectChanges();

    expect(vehicleService.getVehicles).toHaveBeenCalled();
  });

  it('should handle error when loading vehicles', () => {
    vehicleService.getVehicles.and.returnValue(throwError(() => new Error('Test error')));

    fixture.detectChanges();

    expect(component.error()).toBeTruthy();
  });

  it('should call window.print when printQrCodes is called', () => {
    spyOn(window, 'print');
    component.printQrCodes();
    expect(window.print).toHaveBeenCalled();
  });
});

