"""Reservation models for calendar events and Valkey storage."""
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, List


# Legacy Google Calendar models (kept for backward compatibility)
class ReservationCreate(BaseModel):
    """Model for creating a new reservation (legacy Google Calendar)."""
    indicatif: str = Field(..., description="Vehicle radio code (indicatif)")
    chauffeur: str = Field(..., description="Driver name (Nom Prénom)")
    mission: str = Field(..., description="Mission description")
    start: datetime = Field(..., description="Start datetime (ISO 8601)")
    end: datetime = Field(..., description="End datetime (ISO 8601)")
    description: Optional[str] = Field(None, description="Additional technical information")


class ReservationResponse(BaseModel):
    """Model for reservation response (legacy Google Calendar)."""
    id: str = Field(..., description="Event ID")
    indicatif: str = Field(..., description="Vehicle radio code")
    chauffeur: str = Field(..., description="Driver name")
    mission: str = Field(..., description="Mission description")
    start: datetime = Field(..., description="Start datetime")
    end: datetime = Field(..., description="End datetime")
    description: Optional[str] = Field(None, description="Additional information")
    color_id: Optional[str] = Field(None, description="Calendar color ID")


# New Valkey-based models
class ValkeyReservationCreate(BaseModel):
    """Model for creating a new reservation in Valkey."""
    vehicule_immat: str = Field(..., description="Vehicle license plate (immatriculation)")
    chauffeur_nivol: str = Field(..., description="Driver NIVOL identifier")
    chauffeur_nom: str = Field(..., description="Driver full name")
    mission: str = Field(..., description="Mission description")
    debut: datetime = Field(..., description="Start datetime (ISO 8601)")
    fin: datetime = Field(..., description="End datetime (ISO 8601)")
    lieu_depart: Optional[str] = Field(None, description="Departure location")
    commentaire: Optional[str] = Field(None, description="Additional comments")


class ValkeyReservation(ValkeyReservationCreate):
    """Model for a complete reservation stored in Valkey."""
    id: str = Field(..., description="Unique reservation ID (UUID)")
    created_by: str = Field(..., description="Email of user who created the reservation")
    created_at: datetime = Field(..., description="Creation timestamp")
    google_event_id: Optional[str] = Field(None, description="Google Calendar event ID (if synced)")
    google_event_link: Optional[str] = Field(None, description="Google Calendar event HTML link (if synced)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "vehicule_immat": "AB-123-CD",
                "chauffeur_nivol": "123456",
                "chauffeur_nom": "Jean DUPONT",
                "mission": "Formation PSC1",
                "debut": "2026-03-15T08:00:00Z",
                "fin": "2026-03-15T18:00:00Z",
                "lieu_depart": "45 rue de la Paix",
                "commentaire": "Prévoir matériel pédagogique",
                "created_by": "user@croix-rouge.fr",
                "created_at": "2026-03-13T10:00:00Z",
                "google_event_id": "abc123xyz",
                "google_event_link": "https://calendar.google.com/calendar/event?eid=abc123xyz"
            }
        }
    )


class ValkeyReservationListResponse(BaseModel):
    """Response model for listing reservations."""
    count: int = Field(..., description="Number of reservations")
    reservations: List[ValkeyReservation] = Field(..., description="List of reservations")

