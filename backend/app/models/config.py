"""
Configuration models for CLEF API.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class ConfigUpdate(BaseModel):
    """Model for updating configuration (PATCH request)."""

    email_destinataire_alertes: Optional[str] = Field(
        None,
        description="Email destinataire des alertes"
    )
    drive_folder_url: Optional[str] = Field(
        None,
        description="URL du dossier Google Drive racine de la DT"
    )

    @field_validator('email_destinataire_alertes')
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """Validate email format."""
        if v is None:
            return v
        if '@' not in v or '.' not in v.split('@')[1]:
            raise ValueError('Invalid email format')
        return v

    @field_validator('drive_folder_url')
    @classmethod
    def validate_drive_folder_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate that the URL is a Google Drive folder URL."""
        if v is None:
            return v
        if not v.startswith('https://drive.google.com/'):
            raise ValueError('URL must be a Google Drive URL (https://drive.google.com/...)')
        return v


class ConfigResponse(BaseModel):
    """Model for configuration response (GET request)."""

    email_destinataire_alertes: str = Field(
        default="",
        description="Email destinataire des alertes"
    )
    email_gestionnaire_dt: str = Field(
        default="",
        description="Email du gestionnaire DT (lecture seule)"
    )
    drive_folder_id: Optional[str] = Field(
        None,
        description="Identifiant du dossier Google Drive racine"
    )
    drive_folder_url: Optional[str] = Field(
        None,
        description="URL du dossier Google Drive racine"
    )
    drive_sync_status: str = Field(
        default="idle",
        description="Statut de synchronisation Drive (idle, in_progress, complete, error)"
    )
    drive_sync_processed: int = Field(
        default=0,
        description="Nombre de véhicules traités"
    )
    drive_sync_total: int = Field(
        default=0,
        description="Nombre total de véhicules à traiter"
    )
    drive_sync_message: Optional[str] = Field(
        None,
        description="Message de progression"
    )
    drive_sync_error: Optional[str] = Field(
        None,
        description="Dernière erreur de synchronisation"
    )
    drive_sync_current_vehicle: Optional[str] = Field(
        None,
        description="Nom du véhicule en cours de traitement"
    )

