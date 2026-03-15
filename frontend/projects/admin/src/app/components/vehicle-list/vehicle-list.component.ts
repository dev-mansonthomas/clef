import { Component, OnInit, signal, computed, AfterViewInit, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, ActivatedRoute } from '@angular/router';
import { MatTableModule } from '@angular/material/table';
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatSortModule } from '@angular/material/sort';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatButtonModule } from '@angular/material/button';
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
    MatButtonModule,
    FormsModule
  ],
  templateUrl: './vehicle-list.component.html',
  styleUrl: './vehicle-list.component.scss'
})
export class VehicleListComponent implements OnInit, AfterViewInit {
  vehicles = signal<Vehicle[]>([]);
  loading = signal(true);
  searchText = signal('');
  availabilityFilter = signal<'all' | DisponibiliteStatus>('all');
  highlightedImmat = signal<string | null>(null);

  displayedColumns: string[] = [
    'dt_ul',
    'indicatif',
    'immat',
    'status_disponibilite',
    'type',
    'marque_modele',
    'status_ct',
    'status_pollution',
    'assurance',
    'responsable'
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
        v.modele.toLowerCase().includes(search) ||
        v.dt_ul.toLowerCase().includes(search) ||
        v.type.toLowerCase().includes(search)
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
    private router: Router,
    private route: ActivatedRoute,
    private elementRef: ElementRef
  ) {}

  ngOnInit(): void {
    // Check for highlight query param
    this.route.queryParams.subscribe(params => {
      if (params['highlight']) {
        this.highlightedImmat.set(params['highlight']);
        // Scroll after vehicles are loaded
        this.scrollAfterLoad();
      }
    });

    this.loadVehicles();
  }

  ngAfterViewInit(): void {
    // View initialization complete
  }

  loadVehicles(): void {
    this.loading.set(true);
    this.vehicleService.getVehicles().subscribe({
      next: (response) => {
        // Sort vehicles by DT/UL then by Indicatif
        const sortedVehicles = response.vehicles.sort((a, b) => {
          // Primary sort by dt_ul
          const dtCompare = (a.dt_ul || '').localeCompare(b.dt_ul || '');
          if (dtCompare !== 0) return dtCompare;

          // Secondary sort by indicatif
          return (a.indicatif || '').localeCompare(b.indicatif || '');
        });

        this.vehicles.set(sortedVehicles);
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

  onAddVehicle(): void {
    // Navigate to vehicle creation form
    // Using 'new' as a placeholder for creation mode
    this.router.navigate(['/vehicles', 'new', 'edit']);
  }

  getStatusClass(color: string): string {
    return `status-${color}`;
  }

  getPollutionStatusClass(status: { value: string; color: string }): string {
    // N/A en gris (véhicules récents sans contrôle pollution)
    if (status.value === 'N/A') {
      return 'status-gray';
    }
    return `status-${status.color}`;
  }

  getMarqueModele(vehicle: Vehicle): string {
    return `${vehicle.marque} ${vehicle.modele}`;
  }

  /**
   * Check if a vehicle is highlighted
   */
  isHighlighted(vehicle: Vehicle): boolean {
    return this.highlightedImmat() === vehicle.immat;
  }

  /**
   * Wait for vehicles to load, then scroll to highlighted vehicle
   */
  private scrollAfterLoad(): void {
    // Wait for vehicles to load, then scroll
    const checkAndScroll = setInterval(() => {
      if (!this.loading() && this.filteredVehicles().length > 0) {
        clearInterval(checkAndScroll);
        setTimeout(() => this.scrollToHighlightedVehicle(), 100);
      }
    }, 100);

    // Timeout after 5 seconds
    setTimeout(() => clearInterval(checkAndScroll), 5000);
  }

  /**
   * Scroll to highlighted vehicle and apply blink animation
   */
  private scrollToHighlightedVehicle(): void {
    const immat = this.highlightedImmat();
    if (!immat) return;

    // Find the row element
    const rows = this.elementRef.nativeElement.querySelectorAll('tr.clickable-row');
    const vehicles = this.filteredVehicles();

    const vehicleIndex = vehicles.findIndex(v => v.immat === immat);
    if (vehicleIndex === -1) return;

    const row = rows[vehicleIndex];
    if (row) {
      // Scroll into view
      row.scrollIntoView({ behavior: 'smooth', block: 'center' });

      // Add highlight class
      row.classList.add('highlight-blink');

      // Remove highlight class after 4 seconds
      setTimeout(() => {
        row.classList.remove('highlight-blink');
        // Clear the query param
        this.router.navigate([], {
          queryParams: { highlight: null },
          queryParamsHandling: 'merge',
          replaceUrl: true
        });
        this.highlightedImmat.set(null);
      }, 4000);
    }
  }
}

