"""
Service for Google Calendar operations using DT manager's OAuth tokens.
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.services.dt_token_service import dt_token_service
from app.auth.config import auth_settings

logger = logging.getLogger(__name__)


class CalendarService:
    """Service for Google Calendar operations."""

    def __init__(self):
        self.use_mocks = auth_settings.use_mocks

    async def _get_service(self, dt_id: str):
        """Get authenticated Calendar service using DT manager tokens."""
        if self.use_mocks:
            return MockCalendarService()

        access_token = await dt_token_service.get_access_token(dt_id)
        if not access_token:
            raise ValueError(f"No valid tokens for DT {dt_id}")

        credentials = Credentials(token=access_token)
        return build("calendar", "v3", credentials=credentials)

    async def create_calendar(
        self,
        dt_id: str,
        name: str,
        description: str = "",
        timezone: str = "Europe/Paris",
    ) -> Dict[str, Any]:
        """
        Create a new calendar for vehicle reservations.

        Returns:
            Calendar resource with id, summary, etc.
        """
        if self.use_mocks:
            return {
                "id": f"mock-calendar-{dt_id}@group.calendar.google.com",
                "summary": name,
                "description": description,
                "timeZone": timezone,
            }

        service = await self._get_service(dt_id)
        calendar = {
            "summary": name,
            "description": description,
            "timeZone": timezone,
        }

        created = service.calendars().insert(body=calendar).execute()
        logger.info(f"Created calendar {created['id']} for {dt_id}")
        return created

    async def create_event(
        self,
        dt_id: str,
        calendar_id: str,
        summary: str,
        start: datetime,
        end: datetime,
        description: str = "",
        location: str = "",
        attendees: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a calendar event (reservation).

        Returns:
            Event resource with id, htmlLink, etc.
        """
        if self.use_mocks:
            return {
                "id": f"mock-event-{start.isoformat()}",
                "summary": summary,
                "htmlLink": f"https://calendar.google.com/mock-event",
                "start": {"dateTime": start.isoformat()},
                "end": {"dateTime": end.isoformat()},
            }

        service = await self._get_service(dt_id)
        event = {
            "summary": summary,
            "description": description,
            "location": location,
            "start": {"dateTime": start.isoformat(), "timeZone": "Europe/Paris"},
            "end": {"dateTime": end.isoformat(), "timeZone": "Europe/Paris"},
        }

        if attendees:
            event["attendees"] = [{"email": email} for email in attendees]

        created = service.events().insert(calendarId=calendar_id, body=event).execute()
        logger.info(f"Created event {created['id']} in calendar {calendar_id}")
        return created

    async def update_event(
        self,
        dt_id: str,
        calendar_id: str,
        event_id: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update an existing calendar event."""
        if self.use_mocks:
            return {"id": event_id, "updated": True, **updates}

        service = await self._get_service(dt_id)

        # Get existing event
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()

        # Apply updates
        for key, value in updates.items():
            if key in ["start", "end"]:
                event[key] = {"dateTime": value.isoformat(), "timeZone": "Europe/Paris"}
            else:
                event[key] = value

        updated = service.events().update(
            calendarId=calendar_id, eventId=event_id, body=event
        ).execute()
        return updated

    async def delete_event(
        self,
        dt_id: str,
        calendar_id: str,
        event_id: str,
    ) -> bool:
        """Delete a calendar event."""
        if self.use_mocks:
            return True

        service = await self._get_service(dt_id)
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        logger.info(f"Deleted event {event_id} from calendar {calendar_id}")
        return True

    async def list_events(
        self,
        dt_id: str,
        calendar_id: str,
        time_min: datetime = None,
        time_max: datetime = None,
        max_results: int = 100,
    ) -> List[Dict[str, Any]]:
        """List events from calendar."""
        if self.use_mocks:
            return []

        service = await self._get_service(dt_id)

        params = {
            "calendarId": calendar_id,
            "maxResults": max_results,
            "singleEvents": True,
            "orderBy": "startTime",
        }

        if time_min:
            params["timeMin"] = time_min.isoformat() + "Z"
        if time_max:
            params["timeMax"] = time_max.isoformat() + "Z"

        events = service.events().list(**params).execute()
        return events.get("items", [])


class MockCalendarService:
    """Mock calendar service for testing."""
    pass


# Global instance
calendar_service = CalendarService()

