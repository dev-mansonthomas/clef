"""Vehicle data models and schemas."""
from datetime import date, datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class StatusColor(str, Enum):
    """Status color indicators."""
    RED = "red"
    ORANGE = "orange"
    GREEN = "green"


class DisponibiliteStatus(str, Enum):
    """Vehicle availability status."""
    DISPO = "Dispo"
    INDISPO = "Indispo"


class StatusInfo(BaseModel):
    """Status information with color coding."""
    value: str
    color: StatusColor
    days_until_expiry: Optional[int] = None


class VehicleBase(BaseModel):
    """Base vehicle model with all 19 columns from the referential."""
    dt_ul: str = Field(..., description="Délégation Territoriale ou Unité Locale")
    immat: str = Field(..., description="Immatriculation")
    indicatif: str = Field(..., description="Code radio")
    operationnel_mecanique: DisponibiliteStatus = Field(..., description="Disponibilité mécanique")
    raison_indispo: str = Field(default="", description="Raison d'indisponibilité")
    prochain_controle_technique: Optional[str] = Field(None, description="Date du prochain CT (YYYY-MM-DD)")
    prochain_controle_pollution: Optional[str] = Field(None, description="Date du prochain contrôle pollution (YYYY-MM-DD)")
    marque: str = Field(..., description="Marque du véhicule")
    modele: str = Field(..., description="Modèle du véhicule")
    type: str = Field(..., description="Type de véhicule (VSAV, VL, VPSP, etc.)")
    date_mec: Optional[str] = Field(None, description="Date de mise en circulation (YYYY-MM-DD)")
    nom_synthetique: str = Field(..., description="Nom synthétique unique (pour QR code)")
    carte_grise: str = Field(..., description="Numéro de carte grise")
    nb_places: str = Field(..., description="Nombre de places")
    commentaires: str = Field(default="", description="Commentaires libres")
    lieu_stationnement: str = Field(..., description="Lieu de stationnement")
    instructions_recuperation: str = Field(default="", description="Lien vers instructions de récupération")
    assurance_2026: str = Field(default="", description="Informations assurance")
    numero_serie_baus: str = Field(default="", description="Numéro de série BAUS")


class Vehicle(VehicleBase):
    """Vehicle model with computed status fields."""
    status_ct: StatusInfo = Field(..., description="Statut du contrôle technique")
    status_pollution: StatusInfo = Field(..., description="Statut du contrôle pollution")
    status_disponibilite: StatusInfo = Field(..., description="Statut de disponibilité")

    class Config:
        json_schema_extra = {
            "example": {
                "dt_ul": "UL Paris 15",
                "immat": "AB-123-CD",
                "indicatif": "PARIS-15-01",
                "operationnel_mecanique": "Dispo",
                "raison_indispo": "",
                "prochain_controle_technique": "2026-08-15",
                "prochain_controle_pollution": "2026-08-15",
                "marque": "Renault",
                "modele": "Master",
                "type": "VSAV",
                "date_mec": "2020-03-10",
                "nom_synthetique": "VSAV-PARIS15-01",
                "carte_grise": "CG123456789",
                "nb_places": "3",
                "commentaires": "Véhicule principal de l'UL",
                "lieu_stationnement": "Garage UL Paris 15",
                "instructions_recuperation": "https://docs.google.com/document/d/...",
                "assurance_2026": "Contrat #2026-001",
                "numero_serie_baus": "BAUS-2020-001",
                "status_ct": {
                    "value": "2026-08-15",
                    "color": "green",
                    "days_until_expiry": 157
                },
                "status_pollution": {
                    "value": "2026-08-15",
                    "color": "green",
                    "days_until_expiry": 157
                },
                "status_disponibilite": {
                    "value": "Dispo",
                    "color": "green"
                }
            }
        }


class VehicleUpdate(BaseModel):
    """Model for updating vehicle metadata (calendar color, etc.)."""
    couleur_calendrier: Optional[str] = Field(None, description="Couleur pour le calendrier (hex color)")
    commentaires: Optional[str] = Field(None, description="Commentaires libres")
    
    class Config:
        json_schema_extra = {
            "example": {
                "couleur_calendrier": "#FF5733",
                "commentaires": "Véhicule principal de l'UL"
            }
        }


class VehicleListResponse(BaseModel):
    """Response model for vehicle list endpoint."""
    count: int
    vehicles: list[Vehicle]

