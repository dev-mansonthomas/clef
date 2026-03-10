import { Component, OnInit, OnDestroy, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { FullCalendarModule } from '@fullcalendar/angular';
import { CalendarOptions, EventInput } from '@fullcalendar/core';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import frLocale from '@fullcalendar/core/locales/fr';
import { CalendarService } from '../../services/calendar.service';

interface CalendarEvent {
  id: string;
  summary: string;
  start: { dateTime: string; timeZone: string };
  end: { dateTime: string; timeZone: string };
  colorId?: string;
}

interface VehicleMetadata {
  nom_synthetique: string;
  couleur_calendrier?: string;
}

@Component({
  selector: 'app-calendar-view',
  standalone: true,
  imports: [
    CommonModule,
    FullCalendarModule,
    MatButtonModule,
    MatSnackBarModule,
    MatProgressSpinnerModule
  ],
  templateUrl: './calendar-view.component.html',
  styleUrls: ['./calendar-view.component.scss']
})
export class CalendarViewComponent implements OnInit, OnDestroy {
  private readonly calendarService = inject(CalendarService);
  private readonly snackBar = inject(MatSnackBar);
  private refreshInterval?: number;

  // Calendar status
  calendarExists = signal<boolean>(false);
  calendarLoading = signal<boolean>(true);
  creatingCalendar = signal<boolean>(false);
  
  calendarOptions = signal<CalendarOptions>({
    plugins: [timeGridPlugin, interactionPlugin],
    initialView: 'timeGridWeek',
    locale: frLocale,
    headerToolbar: {
      left: 'prev,next today',
      center: 'title',
      right: 'timeGridWeek,timeGridDay'
    },
    slotMinTime: '06:00:00',
    slotMaxTime: '22:00:00',
    allDaySlot: false,
    height: 'auto',
    editable: false,
    selectable: false,
    selectMirror: false,
    dayMaxEvents: true,
    weekends: true,
    events: [],
    eventClick: this.handleEventClick.bind(this),
    eventDidMount: this.handleEventDidMount.bind(this)
  });

  ngOnInit(): void {
    this.checkCalendarStatus();
    // Auto-refresh every 5 minutes
    this.refreshInterval = window.setInterval(() => {
      this.checkCalendarStatus();
    }, 5 * 60 * 1000);
  }

  ngOnDestroy(): void {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
    }
  }

  /**
   * Check if calendar exists and load events if it does
   */
  private checkCalendarStatus(): void {
    this.calendarLoading.set(true);
    this.calendarService.getCalendarStatus().subscribe({
      next: (status) => {
        this.calendarExists.set(status.exists);
        this.calendarLoading.set(false);
        if (status.exists) {
          this.loadEvents();
        }
      },
      error: (error) => {
        console.error('Error checking calendar status:', error);
        this.calendarLoading.set(false);
        this.snackBar.open('Erreur lors de la vérification du calendrier', 'Fermer', {
          duration: 5000
        });
      }
    });
  }

  /**
   * Create a new calendar
   */
  createCalendar(): void {
    this.creatingCalendar.set(true);
    this.calendarService.createCalendar().subscribe({
      next: (response) => {
        this.creatingCalendar.set(false);
        this.calendarExists.set(true);
        this.snackBar.open(
          `Calendrier "${response.summary}" créé avec succès !`,
          'Fermer',
          { duration: 5000 }
        );
        // Load events after calendar creation
        this.loadEvents();
      },
      error: (error) => {
        console.error('Error creating calendar:', error);
        this.creatingCalendar.set(false);
        const message = error.error?.detail || 'Erreur lors de la création du calendrier';
        this.snackBar.open(message, 'Fermer', {
          duration: 5000
        });
      }
    });
  }

  private async loadEvents(): Promise<void> {
    try {
      // TODO: Replace with actual API call when backend endpoint is ready
      // const response = await fetch('http://localhost:8000/api/calendar/events');
      // const data = await response.json();
      
      // Mock data for development
      const mockEvents = this.getMockEvents();
      const vehicleColors = await this.getVehicleColors();
      
      const formattedEvents: EventInput[] = mockEvents.map(event => {
        const indicatif = this.extractIndicatif(event.summary);
        const color = vehicleColors[indicatif] || '#3788d8';
        
        return {
          id: event.id,
          title: event.summary,
          start: event.start.dateTime,
          end: event.end.dateTime,
          backgroundColor: color,
          borderColor: color,
          extendedProps: {
            indicatif,
            colorId: event.colorId
          }
        };
      });

      this.calendarOptions.update(options => ({
        ...options,
        events: formattedEvents
      }));
    } catch (error) {
      console.error('Error loading calendar events:', error);
    }
  }

  private extractIndicatif(summary: string): string {
    // Extract indicatif from format: "{indicatif} - {chauffeur} - {mission}"
    const parts = summary.split(' - ');
    return parts[0] || '';
  }

  private async getVehicleColors(): Promise<Record<string, string>> {
    try {
      // TODO: Replace with actual API call when backend is ready
      // const response = await fetch('http://localhost:8000/api/vehicles');
      // const data = await response.json();
      
      // Mock vehicle colors
      return {
        'VL75-01': '#FF5733',
        'VL75-02': '#33FF57',
        'VL75-03': '#3357FF',
        'VPSP75-01': '#FF33F5',
        'VPSP75-02': '#F5FF33'
      };
    } catch (error) {
      console.error('Error loading vehicle colors:', error);
      return {};
    }
  }

  private getMockEvents(): CalendarEvent[] {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

    // Create events for the current week
    return [
      {
        id: 'mock-1',
        summary: 'VL75-01 - Jean Dupont - Mission Secours',
        start: {
          dateTime: new Date(today.getTime() + 10 * 60 * 60 * 1000).toISOString(),
          timeZone: 'Europe/Paris'
        },
        end: {
          dateTime: new Date(today.getTime() + 14 * 60 * 60 * 1000).toISOString(),
          timeZone: 'Europe/Paris'
        },
        colorId: '5'
      },
      {
        id: 'mock-2',
        summary: 'VL75-02 - Marie Martin - Transport Matériel',
        start: {
          dateTime: new Date(today.getTime() + 1 * 24 * 60 * 60 * 1000 + 8 * 60 * 60 * 1000).toISOString(),
          timeZone: 'Europe/Paris'
        },
        end: {
          dateTime: new Date(today.getTime() + 1 * 24 * 60 * 60 * 1000 + 12 * 60 * 60 * 1000).toISOString(),
          timeZone: 'Europe/Paris'
        },
        colorId: '2'
      },
      {
        id: 'mock-3',
        summary: 'VPSP75-01 - Pierre Durand - Maraude',
        start: {
          dateTime: new Date(today.getTime() + 2 * 24 * 60 * 60 * 1000 + 14 * 60 * 60 * 1000).toISOString(),
          timeZone: 'Europe/Paris'
        },
        end: {
          dateTime: new Date(today.getTime() + 2 * 24 * 60 * 60 * 1000 + 18 * 60 * 60 * 1000).toISOString(),
          timeZone: 'Europe/Paris'
        },
        colorId: '7'
      },
      {
        id: 'mock-4',
        summary: 'VL75-03 - Sophie Bernard - Formation',
        start: {
          dateTime: new Date(today.getTime() + 3 * 24 * 60 * 60 * 1000 + 9 * 60 * 60 * 1000).toISOString(),
          timeZone: 'Europe/Paris'
        },
        end: {
          dateTime: new Date(today.getTime() + 3 * 24 * 60 * 60 * 1000 + 17 * 60 * 60 * 1000).toISOString(),
          timeZone: 'Europe/Paris'
        },
        colorId: '3'
      },
      {
        id: 'mock-5',
        summary: 'VPSP75-02 - Luc Petit - Intervention Urgente',
        start: {
          dateTime: new Date(today.getTime() + 4 * 24 * 60 * 60 * 1000 + 6 * 60 * 60 * 1000).toISOString(),
          timeZone: 'Europe/Paris'
        },
        end: {
          dateTime: new Date(today.getTime() + 4 * 24 * 60 * 60 * 1000 + 10 * 60 * 60 * 1000).toISOString(),
          timeZone: 'Europe/Paris'
        },
        colorId: '9'
      }
    ];
  }

  private handleEventClick(info: any): void {
    // Read-only calendar - just show event details
    console.log('Event clicked:', info.event.title);
  }

  private handleEventDidMount(info: any): void {
    // Additional styling or tooltips can be added here
    info.el.title = info.event.title;
  }
}

