import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PriseFormComponent } from '../../components/prise-form/prise-form.component';

/**
 * Vehicle pickup feature component - wraps the prise form
 */
@Component({
  selector: 'app-prise',
  standalone: true,
  imports: [CommonModule, PriseFormComponent],
  templateUrl: './prise.component.html',
  styleUrl: './prise.component.scss'
})
export class PriseComponent {
}

