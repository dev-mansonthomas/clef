import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { vi } from 'vitest';
import { LayoutComponent } from './layout.component';
import { AuthService } from '../../services/auth.service';
import { VehicleService } from '../../services/vehicle.service';
import { ConfigService } from '../../services/config.service';
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

  const setup = async (role: string, isSuperAdmin: boolean) => {
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
            isSuperAdmin: (u: User | null) => u?.is_super_admin === true
          }
        },
        // `ngOnInit` appelle `checkTutorialAutoShow`, qui interroge ces deux
        // services. Sans doubles, le `forkJoin` échoue et la branche d'erreur
        // ouvre le tutoriel « par défaut sûr » : l'état de départ deviendrait
        // non déterministe. On simule donc une configuration déjà complète.
        {
          provide: VehicleService,
          useValue: { getVehicles: vi.fn(() => of({ count: 3, vehicles: [] })) }
        },
        {
          provide: ConfigService,
          useValue: {
            getConfig: vi.fn(() =>
              of({ drive_folder_url: 'https://drive.google.com/drive/folders/test' })
            )
          }
        }
      ]
    }).compileComponents();

    const fixture = TestBed.createComponent(LayoutComponent);
    fixture.detectChanges();
    return fixture;
  };

  const textOf = (fixture: { nativeElement: unknown }) =>
    (fixture.nativeElement as HTMLElement).textContent ?? '';

  it('should reveal the configuration tutorial from the help button', async () => {
    const fixture = await setup('Gestionnaire DT', false);

    // Le tutoriel est un panneau inline piloté par le signal `showTutorial`, et
    // non un MatDialog : la version précédente de ce test attendait
    // `MatDialog.open`, un mécanisme que le composant n'utilise nulle part —
    // elle ne pouvait donc jamais passer.
    const host = fixture.nativeElement as HTMLElement;
    expect(host.querySelector('.tutorial-panel')).toBeNull();

    const button = host.querySelector<HTMLButtonElement>(
      '[aria-label="Aide à la configuration"]'
    );
    expect(button).not.toBeNull();
    button!.click();
    fixture.detectChanges();

    expect(host.querySelector('.tutorial-panel')).not.toBeNull();
    expect(textOf(fixture)).toContain('Guide de configuration');
  });

  it('should display the Super Admin link for a super admin user', async () => {
    const fixture = await setup('Gestionnaire DT', true);

    expect(textOf(fixture)).toContain('Super Admin');
  });

  it('should hide the Super Admin link for a non super admin user', async () => {
    const fixture = await setup('Gestionnaire DT', false);

    expect(textOf(fixture)).not.toContain('Super Admin');
  });

  it('should display the UL configuration link for UL responsables only', async () => {
    const fixture = await setup('Responsable UL', false);

    expect(textOf(fixture)).toContain('Configuration UL');
    expect(textOf(fixture)).not.toContain('Administration DT');
  });

  it('should hide the UL configuration link for DT managers', async () => {
    const fixture = await setup('Gestionnaire DT', false);

    expect(textOf(fixture)).not.toContain('Configuration UL');
  });
});
