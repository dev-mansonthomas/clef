"""Google Calendar service for managing vehicle reservations."""
import os
from typing import Any, Dict, List, Optional
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import redis


class CalendarService:
    """Service for managing Google Calendar events and calendars."""
    
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    REDIS_CALENDAR_KEY = "clef:calendar:id"
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Initialize the Calendar service.
        
        Args:
            redis_client: Redis client for storing calendar IDs (optional)
        """
        self.redis_client = redis_client
        self._service = None
        self._calendar_id_cache = None
    
    def _get_service(self):
        """Get or create the Google Calendar API service."""
        if self._service is None:
            credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if not credentials_path:
                raise ValueError("GOOGLE_APPLICATION_CREDENTIALS not set")
            
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=self.SCOPES
            )
            self._service = build('calendar', 'v3', credentials=credentials)
        
        return self._service
    
    def _get_calendar_name(self) -> str:
        """Get the calendar name based on environment."""
        env = os.getenv("ENVIRONMENT", "dev").upper()
        prefix = os.getenv("CALENDAR_NAME_PREFIX", f"{env} - CLEF")
        return f"{prefix} - Réservation Véhicule"
    
    def _get_stored_calendar_id(self) -> Optional[str]:
        """Get calendar ID from Redis cache."""
        if self._calendar_id_cache:
            return self._calendar_id_cache
        
        if self.redis_client:
            try:
                calendar_id = self.redis_client.get(self.REDIS_CALENDAR_KEY)
                if calendar_id:
                    self._calendar_id_cache = calendar_id
                    return calendar_id
            except Exception:
                pass
        
        return None
    
    def _store_calendar_id(self, calendar_id: str) -> None:
        """Store calendar ID in Redis."""
        self._calendar_id_cache = calendar_id
        if self.redis_client:
            try:
                self.redis_client.set(self.REDIS_CALENDAR_KEY, calendar_id)
            except Exception:
                pass
    
    def create_calendar(
        self,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        timezone: str = "Europe/Paris"
    ) -> Dict[str, Any]:
        """
        Create a new calendar for vehicle reservations.
        
        Args:
            summary: Calendar name (defaults to environment-specific name)
            description: Calendar description
            timezone: Calendar timezone
            
        Returns:
            Calendar metadata including ID
        """
        service = self._get_service()
        
        if summary is None:
            summary = self._get_calendar_name()
        
        if description is None:
            description = f"Calendrier de réservation des véhicules ({os.getenv('ENVIRONMENT', 'dev').upper()})"
        
        calendar_body = {
            'summary': summary,
            'description': description,
            'timeZone': timezone
        }
        
        try:
            calendar = service.calendars().insert(body=calendar_body).execute()
            self._store_calendar_id(calendar['id'])
            return calendar
        except HttpError as error:
            raise Exception(f"Failed to create calendar: {error}")
    
    def get_calendar_id(self) -> Optional[str]:
        """
        Get the calendar ID from Redis or return None if not set.
        
        Returns:
            Calendar ID or None
        """
        return self._get_stored_calendar_id()
    
    def get_events(
        self,
        calendar_id: Optional[str] = None,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get events from the calendar.
        
        Args:
            calendar_id: Calendar ID (uses stored ID if None)
            time_min: Minimum start time
            time_max: Maximum start time
            max_results: Maximum number of events to return
            
        Returns:
            List of events
        """
        service = self._get_service()
        
        if calendar_id is None:
            calendar_id = self._get_stored_calendar_id()
            if calendar_id is None:
                raise ValueError("No calendar ID available. Create a calendar first.")
        
        params = {
            'calendarId': calendar_id,
            'maxResults': max_results,
            'singleEvents': True,
            'orderBy': 'startTime'
        }

        if time_min:
            params['timeMin'] = time_min.isoformat() + 'Z'
        if time_max:
            params['timeMax'] = time_max.isoformat() + 'Z'

        try:
            events_result = service.events().list(**params).execute()
            return events_result.get('items', [])
        except HttpError as error:
            raise Exception(f"Failed to get events: {error}")

    def create_reservation(
        self,
        indicatif: str,
        chauffeur: str,
        mission: str,
        start: datetime,
        end: datetime,
        description: Optional[str] = None,
        color_id: Optional[str] = None,
        calendar_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a reservation event.

        Args:
            indicatif: Vehicle radio code
            chauffeur: Driver name (Nom Prénom)
            mission: Mission description
            start: Start datetime
            end: End datetime
            description: Additional technical information
            color_id: Event color ID (configurable per vehicle)
            calendar_id: Calendar ID (uses stored ID if None)

        Returns:
            Created event metadata
        """
        service = self._get_service()

        if calendar_id is None:
            calendar_id = self._get_stored_calendar_id()
            if calendar_id is None:
                raise ValueError("No calendar ID available. Create a calendar first.")

        # Format: {indicatif} - {chauffeur} - {mission}
        summary = f"{indicatif} - {chauffeur} - {mission}"

        event_body = {
            'summary': summary,
            'start': {
                'dateTime': start.isoformat(),
                'timeZone': 'Europe/Paris',
            },
            'end': {
                'dateTime': end.isoformat(),
                'timeZone': 'Europe/Paris',
            },
        }

        if description:
            event_body['description'] = description

        if color_id:
            event_body['colorId'] = str(color_id)

        try:
            event = service.events().insert(
                calendarId=calendar_id,
                body=event_body
            ).execute()
            return event
        except HttpError as error:
            raise Exception(f"Failed to create reservation: {error}")

    def delete_reservation(
        self,
        event_id: str,
        calendar_id: Optional[str] = None
    ) -> bool:
        """
        Delete a reservation event.

        Args:
            event_id: Event ID to delete
            calendar_id: Calendar ID (uses stored ID if None)

        Returns:
            True if deleted successfully
        """
        service = self._get_service()

        if calendar_id is None:
            calendar_id = self._get_stored_calendar_id()
            if calendar_id is None:
                raise ValueError("No calendar ID available. Create a calendar first.")

        try:
            service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            return True
        except HttpError as error:
            if error.resp.status == 404:
                return False
            raise Exception(f"Failed to delete reservation: {error}")

