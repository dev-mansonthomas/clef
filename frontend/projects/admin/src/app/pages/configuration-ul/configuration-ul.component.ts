import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AuthService } from '../../services/auth.service';
import { FournisseursManagerComponent } from '../../shared/fournisseurs-manager/fournisseurs-manager.component';

@Component({
  selector: 'app-configuration-ul',
  standalone: true,
  imports: [CommonModule, FournisseursManagerComponent],
  template: `
    <div class="config-ul">
      <h1>Configuration UL — {{ ulName }}</h1>

      <div class="form-section">
        <h2>Fournisseurs</h2>
        <app-fournisseurs-manager [dt]="dt" [niveau]="'ul'"></app-fournisseurs-manager>
      </div>
    </div>
  `,
  styles: [`
    .config-ul {
      padding: 2rem;
      max-width: 1200px;
      margin: 0 auto;
    }
    h1 { color: #E30613; margin-bottom: 1.5rem; }
    .form-section { margin-bottom: 2rem; }
    h2 { color: #333; margin-bottom: 0.5rem; }
  `]
})
export class ConfigurationUlComponent {
  private readonly authService = inject(AuthService);
  ulName = this.authService.currentUserValue?.ul ?? '';
  dt = this.authService.currentUserValue?.dt ?? 'DT75';
}

