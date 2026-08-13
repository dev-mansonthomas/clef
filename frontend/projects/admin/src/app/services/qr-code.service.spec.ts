import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { QrCodeService } from './qr-code.service';

describe('QrCodeService', () => {
  let service: QrCodeService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        QrCodeService,
      ],
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

  it('should generate QR code URL for a vehicle', () => {
    // `generateQrCodeUrl` n'appelle pas le backend : il construit l'URL et émet
    // de façon synchrone. Le `done()` de la version Jasmine était donc inutile
    // autant qu'incompatible avec le runner.
    let emitted: string | undefined;
    service.generateQrCodeUrl('VSAV-TEST-01').subscribe((url) => {
      emitted = url;
    });

    expect(emitted).toBeDefined();
    expect(emitted).toContain('https://');
    expect(emitted).toContain('/vehicle/');
  });

  it('should get QR config from backend', () => {
    const mockConfig = {
      sheets_url_vehicules: 'https://docs.google.com/spreadsheets/test',
      sheets_url_benevoles: 'https://docs.google.com/spreadsheets/test',
      sheets_url_responsables: 'https://docs.google.com/spreadsheets/test',
      template_doc_url: 'https://docs.google.com/document/test',
      email_destinataire_alertes: 'test@example.com',
      email_gestionnaire_dt: 'manager@example.com',
    };

    let received: unknown;
    service.getQrConfig().subscribe((config) => {
      received = config;
    });

    const req = httpMock.expectOne('/api/config');
    expect(req.request.method).toBe('GET');
    req.flush(mockConfig);

    expect(received).toEqual(mockConfig);
  });
});
