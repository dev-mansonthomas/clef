import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map, take } from 'rxjs';

import { AuthService } from '../services/auth.service';

export const ulResponsableGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  return authService.getCurrentUser().pipe(
    take(1),
    map((user) => {
      if (authService.isUlResponsable(user) && !authService.isDTManager(user)) {
        return true;
      }

      router.navigate(['/dashboard']);
      return false;
    })
  );
};