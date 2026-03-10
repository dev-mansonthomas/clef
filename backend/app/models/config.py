"""
Configuration models for CLEF API.
"""
from pydantic import BaseModel, Field, field_validator, HttpUrl
from typing import Optional


class ConfigUpdate(BaseModel):
    """Model for updating configuration (PATCH request)."""
    
    sheets_url_vehicules: Optional[str] = Field(
        None,
        description="URL du référentiel véhicules (Google Sheets)"
    )
    sheets_url_benevoles: Optional[str] = Field(
        None,
        description="URL du référentiel bénévoles (Google Sheets)"
    )
    sheets_url_responsables: Optional[str] = Field(
        None,
        description="URL du référentiel responsables (Google Sheets)"
    )
    template_doc_url: Optional[str] = Field(
        None,
        description="URL du template de document véhicule"
    )
    email_destinataire_alertes: Optional[str] = Field(
        None,
        description="Email destinataire des alertes"
    )
    
    @field_validator('sheets_url_vehicules', 'sheets_url_benevoles', 'sheets_url_responsables', 'template_doc_url')
    @classmethod
    def validate_google_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate that URLs are Google Docs/Sheets URLs."""
        if v is None:
            return v
        if not v.startswith('https://docs.google.com/'):
            raise ValueError('URL must be a Google Docs/Sheets URL (https://docs.google.com/...)')
        return v
    
    @field_validator('email_destinataire_alertes')
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """Validate email format."""
        if v is None:
            return v
        if '@' not in v or '.' not in v.split('@')[1]:
            raise ValueError('Invalid email format')
        return v


class ConfigResponse(BaseModel):
    """Model for configuration response (GET request)."""
    
    sheets_url_vehicules: str = Field(
        ...,
        description="URL du référentiel véhicules (Google Sheets)"
    )
    sheets_url_benevoles: str = Field(
        ...,
        description="URL du référentiel bénévoles (Google Sheets)"
    )
    sheets_url_responsables: str = Field(
        ...,
        description="URL du référentiel responsables (Google Sheets)"
    )
    template_doc_url: str = Field(
        ...,
        description="URL du template de document véhicule"
    )
    email_destinataire_alertes: str = Field(
        ...,
        description="Email destinataire des alertes"
    )
    email_gestionnaire_dt: str = Field(
        ...,
        description="Email du gestionnaire DT (lecture seule)"
    )

