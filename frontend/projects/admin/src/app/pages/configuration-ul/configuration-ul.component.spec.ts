import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { AuthService } from '../../services/auth.service';
import { ConfigurationUlComponent } from './configuration-ul.component';

describe('ConfigurationUlComponent', () => {
  it('should display the connected user UL name', async () => {
    await TestBed.configureTestingModule({
      imports: [ConfigurationUlComponent],
      providers: [
        {
          provide: AuthService,
          useValue: {
            currentUser$: of({ ul: 'UL Paris 15', perimetre: 'UL Paris 15' }),
            currentUserValue: { ul: 'UL Paris 15', perimetre: 'UL Paris 15' }
          }
        }
      ]
    }).compileComponents();

    const fixture = TestBed.createComponent(ConfigurationUlComponent);
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('UL Paris 15');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Aucune configuration disponible');
  });
});