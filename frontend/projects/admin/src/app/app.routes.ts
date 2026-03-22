import { Routes } from '@angular/router';
import { LoginComponent } from './features/auth/login/login.component';
import { LayoutComponent } from './shared/layout/layout.component';
import { authGuard } from './core/guards/auth.guard';
import { dtManagerGuard } from './guards/dt-manager.guard';
import { superAdminGuard } from './guards/super-admin.guard';
import { ulResponsableGuard } from './guards/ul-responsable.guard';

export const routes: Routes = [
  {
    path: 'login',
    component: LoginComponent
  },
  {
    path: 'approbation/:token',
    loadComponent: () => import('./approbation/approbation-page.component')
      .then(m => m.ApprobationPageComponent),
    canActivate: [authGuard],
  },
  {
    path: '',
    component: LayoutComponent,
    canActivate: [authGuard],
    children: [
      {
        path: 'dashboard',
        loadComponent: () => import('./features/dashboard/dashboard.component')
          .then(m => m.DashboardComponent),
      },
      {
        path: 'vehicles',
        loadComponent: () => import('./components/vehicle-list/vehicle-list.component')
          .then(m => m.VehicleListComponent),
      },
      {
        path: 'vehicles/new/edit',
        loadComponent: () => import('./vehicles/vehicle-edit/vehicle-edit')
          .then(m => m.VehicleEdit),
      },
      {
        path: 'vehicles/:immat/edit',
        loadComponent: () => import('./vehicles/vehicle-edit/vehicle-edit')
          .then(m => m.VehicleEdit),
      },
      {
        path: 'vehicles/import',
        loadComponent: () => import('./features/import-vehicles/import-wizard.component')
          .then(m => m.ImportWizardComponent),
      },
      {
        path: 'calendar',
        loadComponent: () => import('./components/calendar-view/calendar-view.component')
          .then(m => m.CalendarViewComponent),
      },
      {
        path: 'qr-codes',
        loadComponent: () => import('./components/qr-code-generator/qr-code-generator.component')
          .then(m => m.QrCodeGeneratorComponent),
      },
      {
        path: 'config',
        loadComponent: () => import('./pages/config/config-page.component')
          .then(m => m.ConfigPageComponent),
        canActivate: [dtManagerGuard]
      },
      {
        path: 'configuration-ul',
        loadComponent: () => import('./pages/configuration-ul/configuration-ul.component')
          .then((m) => m.ConfigurationUlComponent),
        canActivate: [ulResponsableGuard]
      },
      {
        path: 'dt-admin',
        loadComponent: () => import('./components/dt-admin/dt-admin.component')
          .then(m => m.DtAdminComponent),
        canActivate: [dtManagerGuard]
      },
      {
        path: 'super-admin',
        loadComponent: () => import('./pages/super-admin/super-admin.component')
          .then(m => m.SuperAdminComponent),
        canActivate: [superAdminGuard]
      },
      {
        path: '',
        redirectTo: 'dashboard',
        pathMatch: 'full'
      }
    ]
  }
];
