import { Component, inject, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { AuthService } from '../../../services/auth.service';

/**
 * Login component handling Okta authentication
 */
@Component({
  selector: 'app-login',
  imports: [MatButtonModule, MatCardModule],
  templateUrl: './login.component.html',
  styleUrl: './login.component.scss'
})
export class LoginComponent implements OnInit {
  private readonly authService = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  ngOnInit(): void {
    // Check if user is already authenticated
    this.authService.getCurrentUser().subscribe(user => {
      if (user) {
        // Redirect to return URL or dashboard
        const returnUrl = this.route.snapshot.queryParams['returnUrl'] || '/dashboard';
        this.router.navigate([returnUrl]);
      }
    });
  }

  /**
   * Initiate login flow
   */
  login(): void {
    this.authService.login();
  }
}

