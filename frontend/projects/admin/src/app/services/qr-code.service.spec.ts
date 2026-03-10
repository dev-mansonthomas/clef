import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { QrCodeService } from './qr-code.service';

describe('QrCodeService', () => {
  let service: QrCodeService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [QrCodeService]
    });
    service = TestBed.inject(QrCodeService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should generate QR code URL for a vehicle', (done) => {
    const nomSynthetique = 'VSAV-TEST-01';
    
    service.generateQrCodeUrl(nomSynthetique).subscribe(url => {
      expect(url).toContain('/vehicle/');
      expect(url).toContain('https://');
      done();
    });
  });

  it('should get QR config from backend', () => {
    const mockConfig = {
      sheets_url_vehicules: 'https://docs.google.com/spreadsheets/test',
      sheets_url_benevoles: 'https://docs.google.com/spreadsheets/test',
      sheets_url_responsables: 'https://docs.google.com/spreadsheets/test',
      template_doc_url: 'https://docs.google.com/document/test',
      email_destinataire_alertes: 'test@example.com',
      email_gestionnaire_dt: 'manager@example.com'
    };

    service.getQrConfig().subscribe(config => {
      expect(config).toEqual(mockConfig);
    });

    const req = httpMock.expectOne('/api/config');
    expect(req.request.method).toBe('GET');
    req.flush(mockConfig);
  });
});

