"""Calendar data models and schemas."""
from typing import Optional
from pydantic import BaseModel, Field


class CalendarStatusResponse(BaseModel):
    """Response model for calendar status check."""
    exists: bool = Field(..., description="Whether the calendar exists")
    calendar_id: Optional[str] = Field(None, description="Calendar ID if it exists")
    calendar_name: Optional[str] = Field(None, description="Calendar name if it exists")
    
    class Config:
        json_schema_extra = {
            "example": {
                "exists": True,
                "calendar_id": "abc123@group.calendar.google.com",
                "calendar_name": "DEV - CLEF - Réservation Véhicule"
            }
        }


class CalendarCreateResponse(BaseModel):
    """Response model for calendar creation."""
    id: str = Field(..., description="Created calendar ID")
    summary: str = Field(..., description="Calendar name")
    description: str = Field(..., description="Calendar description")
    timeZone: str = Field(..., description="Calendar timezone")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "abc123@group.calendar.google.com",
                "summary": "DEV - CLEF - Réservation Véhicule",
                "description": "Calendrier de réservation des véhicules (DEV)",
                "timeZone": "Europe/Paris"
            }
        }

