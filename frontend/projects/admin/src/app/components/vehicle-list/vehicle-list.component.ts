import { Component, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { MatTableModule } from '@angular/material/table';
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatSortModule } from '@angular/material/sort';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { FormsModule } from '@angular/forms';
import { VehicleService } from '../../services/vehicle.service';
import { Vehicle, DisponibiliteStatus } from '../../models/vehicle.model';

@Component({
  selector: 'app-vehicle-list',
  standalone: true,
  imports: [
    CommonModule,
    MatTableModule,
    MatInputModule,
    MatFormFieldModule,
    MatSelectModule,
    MatSortModule,
    MatProgressSpinnerModule,
    FormsModule
  ],
  templateUrl: './vehicle-list.component.html',
  styleUrl: './vehicle-list.component.scss'
})
export class VehicleListComponent implements OnInit {
  vehicles = signal<Vehicle[]>([]);
  loading = signal(true);
  searchText = signal('');
  availabilityFilter = signal<'all' | DisponibiliteStatus>('all');

  displayedColumns: string[] = [
    'indicatif',
    'immat',
    'marque_modele',
    'status_ct',
    'status_pollution',
    'status_disponibilite'
  ];

  filteredVehicles = computed(() => {
    let filtered = this.vehicles();
    
    // Apply search filter
    const search = this.searchText().toLowerCase();
    if (search) {
      filtered = filtered.filter(v =>
        v.indicatif.toLowerCase().includes(search) ||
        v.immat.toLowerCase().includes(search) ||
        v.marque.toLowerCase().includes(search) ||
        v.modele.toLowerCase().includes(search)
      );
    }

    // Apply availability filter
    const availFilter = this.availabilityFilter();
    if (availFilter !== 'all') {
      filtered = filtered.filter(v => v.operationnel_mecanique === availFilter);
    }

    return filtered;
  });

  constructor(
    private vehicleService: VehicleService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.loadVehicles();
  }

  loadVehicles(): void {
    this.loading.set(true);
    this.vehicleService.getVehicles().subscribe({
      next: (response) => {
        this.vehicles.set(response.vehicles);
        this.loading.set(false);
      },
      error: (error) => {
        console.error('Error loading vehicles:', error);
        this.loading.set(false);
      }
    });
  }

  onRowClick(vehicle: Vehicle): void {
    this.router.navigate(['/vehicles', vehicle.nom_synthetique, 'edit']);
  }

  getStatusClass(color: string): string {
    return `status-${color}`;
  }

  getMarqueModele(vehicle: Vehicle): string {
    return `${vehicle.marque} ${vehicle.modele}`;
  }
}

