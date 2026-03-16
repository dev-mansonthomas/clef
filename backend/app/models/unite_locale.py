"""Unité Locale (UL) data models and schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class UniteLocaleBase(BaseModel):
    """Base Unité Locale model."""
    id: str = Field(..., description="ID de l'Unité Locale")
    nom: str = Field(..., description="Nom de l'Unité Locale")
    dt: str = Field(..., description="Code de la Délégation Territoriale")


class UniteLocale(UniteLocaleBase):
    """Unité Locale model with metadata."""
    created_at: Optional[str] = Field(None, description="Date de création (ISO 8601)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "81",
                "nom": "UL 01-02",
                "dt": "DT75",
                "created_at": "2026-03-13T00:00:00Z"
            }
        }


class UniteLocaleCreate(UniteLocaleBase):
    """Model for creating a new Unité Locale."""
    pass


class UniteLocaleUpdate(BaseModel):
    """Model for updating an Unité Locale."""
    nom: Optional[str] = Field(None, description="Nom de l'Unité Locale")
    
    class Config:
        json_schema_extra = {
            "example": {
                "nom": "UL 01-02 Mise à jour"
            }
        }


class UniteLocaleListResponse(BaseModel):
    """Response model for list of Unités Locales."""
    unites_locales: list[UniteLocale] = Field(..., description="Liste des Unités Locales")
    total: int = Field(..., description="Nombre total d'Unités Locales")
    
    class Config:
        json_schema_extra = {
            "example": {
                "unites_locales": [
                    {
                        "id": "81",
                        "nom": "UL 01-02",
                        "dt": "DT75",
                        "created_at": "2026-03-13T00:00:00Z"
                    }
                ],
                "total": 1
            }
        }

