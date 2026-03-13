import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface CalendarStatusResponse {
  exists: boolean;
  calendar_id: string | null;
  calendar_name: string | null;
}

export interface CalendarCreateResponse {
  id: string;
  summary: string;
  description: string;
  timeZone: string;
}

@Injectable({
  providedIn: 'root'
})
export class CalendarService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  /**
   * Check if the calendar exists
   */
  getCalendarStatus(): Observable<CalendarStatusResponse> {
    return this.http.get<CalendarStatusResponse>(`${this.apiUrl}/api/calendar/status`);
  }

  /**
   * Create a new calendar
   */
  createCalendar(): Observable<CalendarCreateResponse> {
    return this.http.post<CalendarCreateResponse>(`${this.apiUrl}/api/calendar/create`, {});
  }
}

