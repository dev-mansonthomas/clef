"""Carnet de Bord (Vehicle Logbook) models."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class PriseVehicule(BaseModel):
    """Model for vehicle pickup (prise) form data."""
    vehicule_id: str = Field(..., description="Vehicle synthetic name (nom_synthetique)")
    benevole_email: str = Field(..., description="Email of the volunteer taking the vehicle")
    benevole_nom: str = Field(..., description="Last name of the volunteer")
    benevole_prenom: str = Field(..., description="First name of the volunteer")
    kilometrage: int = Field(..., description="Odometer reading at pickup", ge=0)
    niveau_carburant: str = Field(..., description="Fuel level (1/4, 1/2, 3/4, Full)")
    etat_general: str = Field(..., description="General condition of the vehicle")
    observations: Optional[str] = Field(default="", description="Additional observations")
    timestamp: Optional[datetime] = Field(default_factory=datetime.now, description="Timestamp of the pickup")
    
    class Config:
        json_schema_extra = {
            "example": {
                "vehicule_id": "VSAV-PARIS15-01",
                "benevole_email": "jean.dupont@croix-rouge.fr",
                "benevole_nom": "Dupont",
                "benevole_prenom": "Jean",
                "kilometrage": 12500,
                "niveau_carburant": "3/4",
                "etat_general": "Bon état",
                "observations": "Petit impact sur le pare-choc avant",
                "timestamp": "2026-03-10T14:30:00"
            }
        }


class RetourVehicule(BaseModel):
    """Model for vehicle return (retour) form data."""
    vehicule_id: str = Field(..., description="Vehicle synthetic name (nom_synthetique)")
    benevole_email: str = Field(..., description="Email of the volunteer returning the vehicle")
    benevole_nom: str = Field(..., description="Last name of the volunteer")
    benevole_prenom: str = Field(..., description="First name of the volunteer")
    kilometrage: int = Field(..., description="Odometer reading at return", ge=0)
    niveau_carburant: str = Field(..., description="Fuel level (1/4, 1/2, 3/4, Full)")
    etat_general: str = Field(..., description="General condition of the vehicle")
    problemes_signales: Optional[str] = Field(default="", description="Any problems to report")
    observations: Optional[str] = Field(default="", description="Additional observations")
    timestamp: Optional[datetime] = Field(default_factory=datetime.now, description="Timestamp of the return")
    
    class Config:
        json_schema_extra = {
            "example": {
                "vehicule_id": "VSAV-PARIS15-01",
                "benevole_email": "jean.dupont@croix-rouge.fr",
                "benevole_nom": "Dupont",
                "benevole_prenom": "Jean",
                "kilometrage": 12580,
                "niveau_carburant": "1/2",
                "etat_general": "Bon état",
                "problemes_signales": "Voyant moteur allumé",
                "observations": "80 km parcourus",
                "timestamp": "2026-03-10T18:30:00"
            }
        }


class CarnetBordResponse(BaseModel):
    """Response model for carnet de bord operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Success or error message")
    spreadsheet_id: Optional[str] = Field(None, description="ID of the Google Sheet where data was written")
    perimetre: Optional[str] = Field(None, description="Perimeter (UL, activité, DT) where data was written")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Prise enregistrée avec succès",
                "spreadsheet_id": "1abc...xyz",
                "perimetre": "UL Paris 15"
            }
        }


class DernierePrise(BaseModel):
    """Model for the last pickup record of a vehicle."""
    vehicule_id: str = Field(..., description="Vehicle synthetic name")
    benevole_nom: str = Field(..., description="Last name of the volunteer")
    benevole_prenom: str = Field(..., description="First name of the volunteer")
    kilometrage: int = Field(..., description="Odometer reading at last pickup")
    niveau_carburant: str = Field(..., description="Fuel level at last pickup")
    etat_general: str = Field(..., description="General condition at last pickup")
    observations: str = Field(default="", description="Observations from last pickup")
    timestamp: str = Field(..., description="Timestamp of the last pickup")
    
    class Config:
        json_schema_extra = {
            "example": {
                "vehicule_id": "VSAV-PARIS15-01",
                "benevole_nom": "Dupont",
                "benevole_prenom": "Jean",
                "kilometrage": 12500,
                "niveau_carburant": "3/4",
                "etat_general": "Bon état",
                "observations": "Petit impact sur le pare-choc avant",
                "timestamp": "2026-03-10T14:30:00"
            }
        }

