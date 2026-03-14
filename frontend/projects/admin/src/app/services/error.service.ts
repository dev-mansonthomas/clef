import { Injectable, inject } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { ErrorDialogComponent, ErrorDialogData } from '../shared/error-dialog/error-dialog.component';

@Injectable({ providedIn: 'root' })
export class ErrorService {
  private readonly dialog = inject(MatDialog);

  showError(data: ErrorDialogData): void {
    this.dialog.open(ErrorDialogComponent, {
      width: '500px',
      data
    });
  }

  handleHttpError(error: any, userMessage: string): void {
    this.showError({
      userMessage,
      technicalDetails: {
        status: error.status,
        statusText: error.statusText,
        url: error.url,
        message: error.message || error.error?.detail
      }
    });
  }
}

