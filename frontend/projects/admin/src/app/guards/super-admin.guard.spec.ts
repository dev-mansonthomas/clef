import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { firstValueFrom, isObservable, of, throwError } from 'rxjs';
import { vi } from 'vitest';
import { AuthService } from '../services/auth.service';
import { User } from '../models/user.model';
import { superAdminGuard } from './super-admin.guard';

describe('superAdminGuard', () => {
  const createUser = (isSuperAdmin: boolean): User => ({
    email: 'super-admin@croix-rouge.fr',
    nom: 'Admin',
    prenom: 'Super',
    dt: 'DT75',
    ul: 'DT Paris',
    role: 'Gestionnaire DT',
    perimetre: 'DT Paris',
    type_perimetre: 'DT',
    is_super_admin: isSuperAdmin
  });

  const routerMock = {
    navigate: vi.fn()
  };

  const runGuard = async (authServiceMock: Partial<AuthService>) => {
    routerMock.navigate.mockReset();
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        { provide: AuthService, useValue: authServiceMock },
        { provide: Router, useValue: routerMock }
      ]
    });

    const result = TestBed.runInInjectionContext(() => superAdminGuard({} as any, {} as any));

    if (isObservable(result)) {
      return firstValueFrom(result);
    }

    return Promise.resolve(result);
  };

  it('should allow a super admin user', async () => {
    const result = await runGuard({
      getCurrentUser: () => of(createUser(true)),
      isSuperAdmin: (user: User | null) => user?.is_super_admin === true
    });

    expect(result).toBe(true);
    expect(routerMock.navigate).not.toHaveBeenCalled();
  });

  it('should redirect a non super admin user to home', async () => {
    const result = await runGuard({
      getCurrentUser: () => of(createUser(false)),
      isSuperAdmin: (user: User | null) => user?.is_super_admin === true
    });

    expect(result).toBe(false);
    expect(routerMock.navigate).toHaveBeenCalledWith(['/']);
  });

  it('should redirect to home when fetching the user fails', async () => {
    const result = await runGuard({
      getCurrentUser: () => throwError(() => new Error('boom')),
      isSuperAdmin: () => false
    });

    expect(result).toBe(false);
    expect(routerMock.navigate).toHaveBeenCalledWith(['/']);
  });
});