import { Routes } from '@angular/router';
import { VehicleSelectorComponent } from './components/vehicle-selector/vehicle-selector.component';
import { PriseComponent } from './features/prise/prise.component';
import { RetourFormComponent } from './components/retour-form/retour-form.component';
import { LoginComponent } from './features/auth/login/login.component';
import { LayoutComponent } from './shared/layout/layout.component';
import { authGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  {
    path: 'login',
    component: LoginComponent
  },
  {
    path: '',
    component: LayoutComponent,
    canActivate: [authGuard],
    children: [
      {
        path: '',
        component: VehicleSelectorComponent
      },
      {
        path: 'vehicle/:encodedId',
        component: VehicleSelectorComponent
      },
      {
        path: 'prise/:nomSynthetique',
        component: PriseComponent
      },
      {
        path: 'retour/:nomSynthetique',
        component: RetourFormComponent
      }
    ]
  }
];
