"""Pydantic models for Valkey data structures."""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class DTConfiguration(BaseModel):
    """Configuration for a Délégation Territoriale."""
    dt: str = Field(..., description="DT identifier (e.g., 'DT75')")
    nom: str = Field(..., description="DT name")
    gestionnaire_email: str = Field(..., description="DT manager email")
    region: Optional[str] = Field(None, description="Region")
    departement: Optional[str] = Field(None, description="Department")


class VehicleData(BaseModel):
    """Vehicle data stored in Valkey."""
    immat: str = Field(..., description="License plate")
    dt: str = Field(..., description="DT identifier")
    dt_ul: Optional[str] = Field(None, description="UL within DT")
    marque: Optional[str] = Field(None, description="Brand")
    modele: Optional[str] = Field(None, description="Model")
    indicatif: Optional[str] = Field(None, description="Call sign")
    nom_synthetique: Optional[str] = Field(None, description="Synthetic name")
    operationnel_mecanique: Optional[str] = Field(None, description="Mechanical status")
    prochain_controle_technique: Optional[str] = Field(None, description="Next technical inspection")
    prochain_controle_pollution: Optional[str] = Field(None, description="Next pollution control")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "immat": "AB-123-CD",
                "dt": "DT75",
                "dt_ul": "81",
                "marque": "Renault",
                "modele": "Master",
                "indicatif": "VPSU 81",
                "nom_synthetique": "vpsu-81",
                "operationnel_mecanique": "Dispo"
            }
        }
    )


class BenevoleData(BaseModel):
    """Bénévole data stored in Valkey."""
    nivol: str = Field(..., description="NIVOL identifier")
    dt: str = Field(..., description="DT identifier")
    ul: Optional[str] = Field(None, description="UL identifier")
    nom: str = Field(..., description="Last name")
    prenom: str = Field(..., description="First name")
    email: Optional[str] = Field(None, description="Email address")
    role: Optional[str] = Field(None, description="Role")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "nivol": "123456",
                "dt": "DT75",
                "ul": "81",
                "nom": "Dupont",
                "prenom": "Jean",
                "email": "jean.dupont@croix-rouge.fr",
                "role": "Bénévole"
            }
        }
    )


class CarnetBordEntry(BaseModel):
    """Carnet de bord entry stored in Valkey."""
    immat: str = Field(..., description="Vehicle license plate")
    dt: str = Field(..., description="DT identifier")
    timestamp: datetime = Field(..., description="Entry timestamp")
    type: str = Field(..., description="Entry type: 'Prise' or 'Retour'")
    benevole_nom: str = Field(..., description="Volunteer last name")
    benevole_prenom: str = Field(..., description="Volunteer first name")
    benevole_email: Optional[str] = Field(None, description="Volunteer email")
    kilometrage: Optional[int] = Field(None, description="Mileage")
    niveau_carburant: Optional[str] = Field(None, description="Fuel level")
    etat_general: Optional[str] = Field(None, description="General condition")
    observations: Optional[str] = Field(None, description="Observations")
    problemes_signales: Optional[str] = Field(None, description="Reported issues (for Retour)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "immat": "AB-123-CD",
                "dt": "DT75",
                "timestamp": "2024-01-15T10:30:00",
                "type": "Prise",
                "benevole_nom": "Dupont",
                "benevole_prenom": "Jean",
                "benevole_email": "jean.dupont@croix-rouge.fr",
                "kilometrage": 12500,
                "niveau_carburant": "3/4",
                "etat_general": "Bon",
                "observations": "RAS"
            }
        }
    )

