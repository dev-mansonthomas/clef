import { Component, OnInit, OnDestroy, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatIconModule } from '@angular/material/icon';
import { FullCalendarModule } from '@fullcalendar/angular';
import { CalendarOptions, EventInput } from '@fullcalendar/core';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import frLocale from '@fullcalendar/core/locales/fr';
import { CalendarService, ValkeyReservation } from '../../services/calendar.service';
import { AuthService } from '../../services/auth.service';

interface VehicleMetadata {
  immat: string;
  indicatif: string;
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
    MatProgressSpinnerModule,
    MatIconModule
  ],
  templateUrl: './calendar-view.component.html',
  styleUrls: ['./calendar-view.component.scss']
})
export class CalendarViewComponent implements OnInit, OnDestroy {
  private readonly calendarService = inject(CalendarService);
  private readonly authService = inject(AuthService);
  private readonly snackBar = inject(MatSnackBar);
  private refreshInterval?: number;

  // User DT
  userDt = signal<string>('DT75'); // Default, will be updated from user

  // Calendar status
  calendarLoading = signal<boolean>(true);
  icalFeedUrl = signal<string>('');

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
    // Get user DT
    this.authService.getCurrentUser().subscribe({
      next: (user) => {
        if (user) {
          this.userDt.set(user.dt || 'DT75');
          this.icalFeedUrl.set(this.calendarService.getICalFeedUrl(this.userDt()));
          this.loadReservations();
        }
      },
      error: (error) => {
        console.error('Error getting user:', error);
        this.calendarLoading.set(false);
      }
    });

    // Auto-refresh every 5 minutes
    this.refreshInterval = window.setInterval(() => {
      this.loadReservations();
    }, 5 * 60 * 1000);
  }

  ngOnDestroy(): void {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
    }
  }

  /**
   * Load reservations from the API
   */
  private loadReservations(): void {
    this.calendarLoading.set(true);
    this.calendarService.getReservations(this.userDt()).subscribe({
      next: (response) => {
        this.calendarLoading.set(false);
        const formattedEvents = this.formatReservationsAsEvents(response.reservations);
        this.calendarOptions.update(options => ({
          ...options,
          events: formattedEvents
        }));
      },
      error: (error) => {
        console.error('Error loading reservations:', error);
        this.calendarLoading.set(false);
        this.snackBar.open('Erreur lors du chargement des réservations', 'Fermer', {
          duration: 5000
        });
      }
    });
  }

  /**
   * Copy iCal feed URL to clipboard
   */
  copyICalUrl(): void {
    const url = this.icalFeedUrl();
    navigator.clipboard.writeText(url).then(() => {
      this.snackBar.open('URL du feed iCal copiée !', 'Fermer', {
        duration: 3000
      });
    }).catch(err => {
      console.error('Failed to copy URL:', err);
      this.snackBar.open('Erreur lors de la copie de l\'URL', 'Fermer', {
        duration: 3000
      });
    });
  }

  /**
   * Format reservations as FullCalendar events
   */
  private formatReservationsAsEvents(reservations: ValkeyReservation[]): EventInput[] {
    return reservations.map(reservation => {
      // Use a default color for now - could be enhanced with vehicle colors later
      const color = this.getColorForVehicle(reservation.vehicule_immat);

      return {
        id: reservation.id,
        title: `${reservation.vehicule_immat} - ${reservation.chauffeur_nom} - ${reservation.mission}`,
        start: reservation.debut,
        end: reservation.fin,
        backgroundColor: color,
        borderColor: color,
        extendedProps: {
          vehicule_immat: reservation.vehicule_immat,
          chauffeur_nivol: reservation.chauffeur_nivol,
          chauffeur_nom: reservation.chauffeur_nom,
          mission: reservation.mission,
          lieu_depart: reservation.lieu_depart,
          commentaire: reservation.commentaire
        }
      };
    });
  }

  /**
   * Get color for a vehicle (simple hash-based color generation)
   */
  private getColorForVehicle(immat: string): string {
    // Simple hash function to generate consistent colors for vehicles
    let hash = 0;
    for (let i = 0; i < immat.length; i++) {
      hash = immat.charCodeAt(i) + ((hash << 5) - hash);
    }

    // Generate a color from the hash
    const hue = Math.abs(hash % 360);
    return `hsl(${hue}, 70%, 50%)`;
  }

  private handleEventClick(info: any): void {
    // Read-only calendar - just show event details
    const props = info.event.extendedProps;
    const details = [
      `Véhicule: ${props.vehicule_immat}`,
      `Chauffeur: ${props.chauffeur_nom}`,
      `Mission: ${props.mission}`,
      props.lieu_depart ? `Lieu de départ: ${props.lieu_depart}` : '',
      props.commentaire ? `Commentaire: ${props.commentaire}` : ''
    ].filter(Boolean).join('\n');

    console.log('Event clicked:', info.event.title, details);
  }

  private handleEventDidMount(info: any): void {
    // Add tooltip with event details
    const props = info.event.extendedProps;
    const tooltip = [
      info.event.title,
      props.lieu_depart ? `Départ: ${props.lieu_depart}` : '',
      props.commentaire ? `Note: ${props.commentaire}` : ''
    ].filter(Boolean).join('\n');

    info.el.title = tooltip;
  }
}

