"""Factory for creating Google API services (real or mock based on environment)."""
import os
from typing import Union

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
    if use_mocks():
        return GoogleSheetsMock()
    
    # TODO: Import and return real Google Sheets service when implemented
    raise NotImplementedError("Real Google Sheets service not yet implemented")


def get_drive_service():
    """
    Get Google Drive service (real or mock).
    
    Returns:
        GoogleDriveMock if USE_MOCKS=true, otherwise real service
    """
    if use_mocks():
        return GoogleDriveMock()
    
    # TODO: Import and return real Google Drive service when implemented
    raise NotImplementedError("Real Google Drive service not yet implemented")


def get_calendar_service():
    """
    Get Google Calendar service (real or mock).
    
    Returns:
        GoogleCalendarMock if USE_MOCKS=true, otherwise real service
    """
    if use_mocks():
        return GoogleCalendarMock()
    
    # TODO: Import and return real Google Calendar service when implemented
    raise NotImplementedError("Real Google Calendar service not yet implemented")


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

