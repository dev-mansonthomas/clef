import { Component, Output, EventEmitter, Input, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';

/**
 * File Upload Component with Drag & Drop
 */
@Component({
  selector: 'app-file-upload',
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatIconModule,
    MatCardModule
  ],
  template: `
    <div 
      class="upload-area"
      [class.dragging]="isDragging()"
      (drop)="onDrop($event)"
      (dragover)="onDragOver($event)"
      (dragleave)="onDragLeave($event)"
    >
      <mat-icon class="upload-icon">cloud_upload</mat-icon>
      
      @if (!selectedFile()) {
        <p class="upload-text">
          Glissez-déposez votre fichier CSV ici
        </p>
        <p class="upload-subtext">ou</p>
        <button mat-raised-button color="primary" (click)="fileInput.click()">
          <mat-icon>folder_open</mat-icon>
          Parcourir
        </button>
      } @else {
        <div class="file-info">
          <mat-icon color="primary">description</mat-icon>
          <div class="file-details">
            <p class="file-name">{{ selectedFile()!.name }}</p>
            <p class="file-size">{{ formatFileSize(selectedFile()!.size) }}</p>
          </div>
          <button mat-icon-button (click)="clearFile()">
            <mat-icon>close</mat-icon>
          </button>
        </div>
      }
      
      <input
        #fileInput
        type="file"
        [accept]="acceptedTypes"
        (change)="onFileInputChange($event)"
        style="display: none"
      />
    </div>
  `,
  styles: [`
    .upload-area {
      border: 2px dashed var(--mat-sys-outline);
      border-radius: 8px;
      padding: 48px 24px;
      text-align: center;
      transition: all 0.3s ease;
      cursor: pointer;
      background-color: var(--mat-sys-surface-container-lowest);

      &.dragging {
        border-color: var(--mat-sys-primary);
        background-color: var(--mat-sys-primary-container);
      }

      &:hover {
        border-color: var(--mat-sys-primary);
      }
    }

    .upload-icon {
      font-size: 64px;
      width: 64px;
      height: 64px;
      color: var(--mat-sys-on-surface-variant);
      margin-bottom: 16px;
    }

    .upload-text {
      font-size: 16px;
      color: var(--mat-sys-on-surface);
      margin: 16px 0 8px;
    }

    .upload-subtext {
      font-size: 14px;
      color: var(--mat-sys-on-surface-variant);
      margin: 8px 0 16px;
    }

    .file-info {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 16px;
      background-color: var(--mat-sys-surface-container);
      border-radius: 8px;
      max-width: 400px;
      margin: 0 auto;

      mat-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
      }

      .file-details {
        flex: 1;
        text-align: left;

        .file-name {
          font-weight: 500;
          margin: 0 0 4px;
        }

        .file-size {
          font-size: 12px;
          color: var(--mat-sys-on-surface-variant);
          margin: 0;
        }
      }
    }
  `]
})
export class FileUploadComponent {
  @Input() acceptedTypes = '.csv';
  @Output() fileSelected = new EventEmitter<File>();
  
  selectedFile = signal<File | null>(null);
  isDragging = signal(false);
  
  onDragOver(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging.set(true);
  }
  
  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging.set(false);
  }
  
  onDrop(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging.set(false);
    
    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
      this.handleFile(files[0]);
    }
  }
  
  onFileInputChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.handleFile(input.files[0]);
    }
  }
  
  private handleFile(file: File): void {
    // Validate file type
    if (!file.name.endsWith('.csv')) {
      alert('Veuillez sélectionner un fichier CSV');
      return;
    }
    
    this.selectedFile.set(file);
    this.fileSelected.emit(file);
  }
  
  clearFile(): void {
    this.selectedFile.set(null);
  }
  
  formatFileSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }
}

