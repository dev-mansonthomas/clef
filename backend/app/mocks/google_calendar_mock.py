"""Mock implementation of Google Calendar API service."""
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta


class GoogleCalendarMock:
    """Mock Google Calendar service for event management."""
    
    def __init__(self):
        """Initialize the mock service."""
        self._calendars: Dict[str, Dict[str, Any]] = {
            "mock-calendar-dev": {
                "id": "mock-calendar-dev",
                "summary": "DEV - CLEF - Réservation Véhicule",
                "description": "Calendrier de réservation des véhicules (DEV)",
                "timeZone": "Europe/Paris"
            }
        }
        self._events: Dict[str, List[Dict[str, Any]]] = {
            "mock-calendar-dev": []
        }
    
    def create_calendar(
        self,
        summary: str,
        description: Optional[str] = None,
        timezone: str = "Europe/Paris"
    ) -> Dict[str, Any]:
        """
        Mock calendar creation.
        
        Args:
            summary: Calendar name
            description: Calendar description
            timezone: Calendar timezone
            
        Returns:
            Mock calendar metadata
        """
        calendar_id = f"mock-calendar-{datetime.now().timestamp()}"
        calendar = {
            "id": calendar_id,
            "summary": summary,
            "description": description or "",
            "timeZone": timezone
        }
        self._calendars[calendar_id] = calendar
        self._events[calendar_id] = []
        return calendar
    
    def get_calendar(self, calendar_id: str) -> Optional[Dict[str, Any]]:
        """
        Get calendar by ID.
        
        Args:
            calendar_id: The calendar ID
            
        Returns:
            Calendar metadata or None if not found
        """
        return self._calendars.get(calendar_id)
    
    def create_event(
        self,
        calendar_id: str,
        summary: str,
        start: datetime,
        end: datetime,
        description: Optional[str] = None,
        color_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Mock event creation.
        
        Args:
            calendar_id: The calendar ID
            summary: Event title
            start: Start datetime
            end: End datetime
            description: Event description
            color_id: Event color ID
            
        Returns:
            Mock event metadata
        """
        event_id = f"mock-event-{datetime.now().timestamp()}"
        event = {
            "id": event_id,
            "summary": summary,
            "description": description or "",
            "start": {"dateTime": start.isoformat(), "timeZone": "Europe/Paris"},
            "end": {"dateTime": end.isoformat(), "timeZone": "Europe/Paris"},
            "colorId": color_id,
            "status": "confirmed"
        }
        
        if calendar_id not in self._events:
            self._events[calendar_id] = []
        
        self._events[calendar_id].append(event)
        return event
    
    def list_events(
        self,
        calendar_id: str,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        List events in a calendar.
        
        Args:
            calendar_id: The calendar ID
            time_min: Minimum start time (optional)
            time_max: Maximum start time (optional)
            
        Returns:
            List of events
        """
        if calendar_id not in self._events:
            return []
        
        events = self._events[calendar_id]
        
        # Filter by time range if provided
        if time_min or time_max:
            filtered_events = []
            for event in events:
                event_start = datetime.fromisoformat(
                    event["start"]["dateTime"].replace("Z", "+00:00")
                )
                
                if time_min and event_start < time_min:
                    continue
                if time_max and event_start > time_max:
                    continue
                
                filtered_events.append(event)
            
            return filtered_events
        
        return events.copy()
    
    def delete_event(self, calendar_id: str, event_id: str) -> bool:
        """
        Delete an event.
        
        Args:
            calendar_id: The calendar ID
            event_id: The event ID
            
        Returns:
            True if deleted, False if not found
        """
        if calendar_id not in self._events:
            return False
        
        events = self._events[calendar_id]
        for i, event in enumerate(events):
            if event["id"] == event_id:
                events.pop(i)
                return True
        
        return False

