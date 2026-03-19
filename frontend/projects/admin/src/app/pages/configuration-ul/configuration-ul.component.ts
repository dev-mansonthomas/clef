import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-configuration-ul',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="config-ul">
      <h1>Configuration UL — {{ ulName }}</h1>
      <p>Aucune configuration disponible</p>
    </div>
  `
})
export class ConfigurationUlComponent {
  private readonly authService = inject(AuthService);
  ulName = this.authService.currentUserValue?.ul ?? '';
}

