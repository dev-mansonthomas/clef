"""Reservation models for calendar events."""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ReservationCreate(BaseModel):
    """Model for creating a new reservation."""
    indicatif: str = Field(..., description="Vehicle radio code (indicatif)")
    chauffeur: str = Field(..., description="Driver name (Nom Prénom)")
    mission: str = Field(..., description="Mission description")
    start: datetime = Field(..., description="Start datetime (ISO 8601)")
    end: datetime = Field(..., description="End datetime (ISO 8601)")
    description: Optional[str] = Field(None, description="Additional technical information")


class ReservationResponse(BaseModel):
    """Model for reservation response."""
    id: str = Field(..., description="Event ID")
    indicatif: str = Field(..., description="Vehicle radio code")
    chauffeur: str = Field(..., description="Driver name")
    mission: str = Field(..., description="Mission description")
    start: datetime = Field(..., description="Start datetime")
    end: datetime = Field(..., description="End datetime")
    description: Optional[str] = Field(None, description="Additional information")
    color_id: Optional[str] = Field(None, description="Calendar color ID")

