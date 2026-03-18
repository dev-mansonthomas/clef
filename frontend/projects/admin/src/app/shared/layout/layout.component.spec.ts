import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { MatDialog } from '@angular/material/dialog';
import { LayoutComponent } from './layout.component';
import { AuthService } from '../../services/auth.service';

describe('LayoutComponent', () => {
  it('should open the configuration tutorial from the help button', async () => {
    let openCalled = false;
    const dialogMock = {
      open: () => {
        openCalled = true;
      }
    };

    await TestBed.configureTestingModule({
      imports: [LayoutComponent],
      providers: [
        provideRouter([]),
        {
          provide: AuthService,
          useValue: {
            currentUser$: of({ prenom: 'Thomas', nom: 'Manson', role: 'Gestionnaire DT' }),
            logout: () => of(void 0),
            isDTManager: () => true
          }
        },
        { provide: MatDialog, useValue: dialogMock }
      ]
    }).compileComponents();

    const fixture = TestBed.createComponent(LayoutComponent);
    fixture.detectChanges();

    const button = fixture.nativeElement.querySelector('[aria-label="Tutoriel de configuration"]');
    button.click();

    expect(openCalled).toBe(true);
  });
});