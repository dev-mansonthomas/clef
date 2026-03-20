import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { MatDialog } from '@angular/material/dialog';
import { vi } from 'vitest';
import { LayoutComponent } from './layout.component';
import { AuthService } from '../../services/auth.service';
import { User } from '../../models/user.model';

describe('LayoutComponent', () => {
  const createUser = (role: string, isSuperAdmin: boolean): User => ({
    email: 'thomas.manson@croix-rouge.fr',
    nom: 'Manson',
    prenom: 'Thomas',
    dt: 'DT75',
    ul: role === 'Responsable UL' ? 'UL Paris 15' : 'DT Paris',
    role,
    perimetre: role === 'Responsable UL' ? 'UL Paris 15' : 'DT Paris',
    type_perimetre: role === 'Responsable UL' ? 'UL' : 'DT',
    is_super_admin: isSuperAdmin
  });

  const dialogMock = {
    open: vi.fn()
  };

  const setup = async (role: string, isSuperAdmin: boolean) => {
    dialogMock.open.mockReset();
    const user = createUser(role, isSuperAdmin);

    await TestBed.configureTestingModule({
      imports: [LayoutComponent],
      providers: [
        provideRouter([]),
        {
          provide: AuthService,
          useValue: {
            currentUser$: of(user),
            logout: () => of(void 0),
            isDTManager: (currentUser: User | null) => currentUser?.role === 'Gestionnaire DT',
            isUlResponsable: (currentUser: User | null) => currentUser?.role === 'Responsable UL',
            isSuperAdmin: (user: User | null) => user?.is_super_admin === true
          }
        },
        { provide: MatDialog, useValue: dialogMock }
      ]
    }).compileComponents();

    const fixture = TestBed.createComponent(LayoutComponent);
    fixture.detectChanges();
    return fixture;
  };

  it('should open the configuration tutorial from the help button', async () => {
    const fixture = await setup('Gestionnaire DT', false);

    const button = fixture.nativeElement.querySelector('[aria-label="Tutoriel de configuration"]');
    button.click();

    expect(dialogMock.open).toHaveBeenCalled();
  });

  it('should display the Super Admin link for a super admin user', async () => {
    const fixture = await setup('Gestionnaire DT', true);

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Super Admin');
  });

  it('should hide the Super Admin link for a non super admin user', async () => {
    const fixture = await setup('Gestionnaire DT', false);

    expect((fixture.nativeElement as HTMLElement).textContent).not.toContain('Super Admin');
  });

  it('should display the UL configuration link for UL responsables only', async () => {
    const fixture = await setup('Responsable UL', false);

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Configuration UL');
    expect((fixture.nativeElement as HTMLElement).textContent).not.toContain('Administration DT');
  });

  it('should hide the UL configuration link for DT managers', async () => {
    const fixture = await setup('Gestionnaire DT', false);

    expect((fixture.nativeElement as HTMLElement).textContent).not.toContain('Configuration UL');
  });
});