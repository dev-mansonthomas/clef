import { Routes } from '@angular/router';
import { VehicleListComponent } from './components/vehicle-list/vehicle-list.component';
import { VehicleEdit } from './vehicles/vehicle-edit/vehicle-edit';
import { CalendarViewComponent } from './components/calendar-view/calendar-view.component';
import { QrCodeGeneratorComponent } from './components/qr-code-generator/qr-code-generator.component';
import { ConfigPageComponent } from './pages/config/config-page.component';
import { DtAdminComponent } from './components/dt-admin/dt-admin.component';
import { LoginComponent } from './features/auth/login/login.component';
import { LayoutComponent } from './shared/layout/layout.component';
import { DashboardComponent } from './features/dashboard/dashboard.component';
import { ImportWizardComponent } from './features/import-vehicles/import-wizard.component';
import { authGuard } from './core/guards/auth.guard';
import { dtManagerGuard } from './guards/dt-manager.guard';

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
        path: 'dashboard',
        component: DashboardComponent
      },
      {
        path: 'vehicles',
        component: VehicleListComponent
      },
      {
        path: 'vehicles/:nomSynthetique/edit',
        component: VehicleEdit
      },
      {
        path: 'vehicles/import',
        component: ImportWizardComponent
      },
      {
        path: 'calendar',
        component: CalendarViewComponent
      },
      {
        path: 'qr-codes',
        component: QrCodeGeneratorComponent
      },
      {
        path: 'config',
        component: ConfigPageComponent,
        canActivate: [dtManagerGuard]
      },
      {
        path: 'dt-admin',
        component: DtAdminComponent,
        canActivate: [dtManagerGuard]
      },
      {
        path: '',
        redirectTo: 'dashboard',
        pathMatch: 'full'
      }
    ]
  }
];
