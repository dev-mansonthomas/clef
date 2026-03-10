"""Factory for creating Google API services (real or mock based on environment)."""
import os
import redis
from typing import Union, Optional

from .google_sheets_mock import GoogleSheetsMock
from .google_drive_mock import GoogleDriveMock
from .google_calendar_mock import GoogleCalendarMock
from .google_gmail_mock import GoogleGmailMock


def use_mocks() -> bool:
    """
    Check if mock services should be used.
    
    Returns:
        True if USE_MOCKS environment variable is set to 'true'
    """
    return os.getenv("USE_MOCKS", "false").lower() == "true"


def get_sheets_service():
    """
    Get Google Sheets service (real or mock).

    Returns:
        GoogleSheetsMock if USE_MOCKS=true, otherwise real service
    """
    # Use the new centralized factory from app.services.sheets
    from app.services.sheets import get_sheets_service as _get_sheets_service
    return _get_sheets_service()


def get_drive_service():
    """
    Get Google Drive service (real or mock).

    Returns:
        GoogleDriveMock if USE_MOCKS=true, otherwise real service
    """
    # Use the new centralized factory from app.services.drive
    from app.services.drive import get_drive_service as _get_drive_service
    return _get_drive_service()


def get_calendar_service(redis_client: Optional[redis.Redis] = None):
    """
    Get Google Calendar service (real or mock).

    Args:
        redis_client: Redis client for storing calendar IDs (optional)

    Returns:
        GoogleCalendarMock if USE_MOCKS=true, otherwise real CalendarService
    """
    if use_mocks():
        return GoogleCalendarMock()

    from app.services.calendar_service import CalendarService
    return CalendarService(redis_client=redis_client)


def get_gmail_service():
    """
    Get Gmail service (real or mock).
    
    Returns:
        GoogleGmailMock if USE_MOCKS=true, otherwise real service
    """
    if use_mocks():
        return GoogleGmailMock()
    
    # TODO: Import and return real Gmail service when implemented
    raise NotImplementedError("Real Gmail service not yet implemented")

