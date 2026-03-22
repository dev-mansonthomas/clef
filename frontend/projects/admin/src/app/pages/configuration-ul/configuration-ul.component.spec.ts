import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { of } from 'rxjs';

import { AuthService } from '../../services/auth.service';
import { ConfigurationUlComponent } from './configuration-ul.component';

describe('ConfigurationUlComponent', () => {
  it('should display the connected user UL name and fournisseurs section', async () => {
    await TestBed.configureTestingModule({
      imports: [ConfigurationUlComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        {
          provide: AuthService,
          useValue: {
            currentUser$: of({ ul: 'UL Paris 15', perimetre: 'UL Paris 15', dt: 'DT75' }),
            currentUserValue: { ul: 'UL Paris 15', perimetre: 'UL Paris 15', dt: 'DT75' }
          }
        }
      ]
    }).compileComponents();

    const fixture = TestBed.createComponent(ConfigurationUlComponent);
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('UL Paris 15');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Fournisseurs');
  });
});