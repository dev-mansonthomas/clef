"""Vehicle data models and schemas."""
from datetime import date, datetime
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator


class StatusColor(str, Enum):
    """Status color indicators."""
    RED = "red"
    ORANGE = "orange"
    GREEN = "green"


class DisponibiliteStatus(str, Enum):
    """Vehicle availability status."""
    DISPO = "Dispo"
    INDISPO = "Indispo"

    @staticmethod
    def normalize(value: str) -> "DisponibiliteStatus":
        """
        Normalize disponibilite value to enum.

        Handles various input formats:
        - "Dispo", "Disponible", "Opérationnel Mécanique" → DISPO
        - "Indispo", "Indisponible" → INDISPO
        - Case-insensitive matching

        Args:
            value: Raw disponibilite value from CSV/Sheets

        Returns:
            DisponibiliteStatus enum value
        """
        if not value:
            return DisponibiliteStatus.INDISPO

        value_lower = value.lower().strip()

        # Map various "available" values to DISPO
        if value_lower in ("dispo", "disponible", "opérationnel mécanique", "operationnel mecanique"):
            return DisponibiliteStatus.DISPO
        # Everything else maps to INDISPO
        else:
            return DisponibiliteStatus.INDISPO


class SuiviMode(str, Enum):
    """Vehicle tracking mode - when the CLEF form should be filled."""
    PRISE = "prise"
    RETOUR = "retour"
    PRISE_ET_RETOUR = "prise_et_retour"

    @staticmethod
    def determine_from_indicatif(indicatif: str) -> "SuiviMode":
        """
        Determine suivi_mode based on vehicle indicatif.

        Rules:
        - Indicatif contains "VPSP" or "LOG" → PRISE_ET_RETOUR
        - Other vehicles → PRISE

        Args:
            indicatif: Vehicle radio code

        Returns:
            SuiviMode enum value
        """
        if not indicatif:
            return SuiviMode.PRISE

        indicatif_upper = indicatif.upper()
        if "VPSP" in indicatif_upper or "LOG" in indicatif_upper:
            return SuiviMode.PRISE_ET_RETOUR

        return SuiviMode.PRISE

    @staticmethod
    def determine_from_type(vehicle_type: str) -> "SuiviMode":
        """
        Determine suivi_mode based on vehicle type.

        Rules:
        - VPSP, LOG, PCM → PRISE_ET_RETOUR (both pickup and return)
        - Other vehicles (VL, VSAV, Quad, etc.) → PRISE (pickup only)

        Args:
            vehicle_type: Vehicle type (VPSP, VL, VSAV, LOG, PCM, etc.)

        Returns:
            SuiviMode enum value
        """
        if not vehicle_type:
            return SuiviMode.PRISE

        vehicle_type_upper = vehicle_type.upper()
        both_types = ['VPSP', 'LOG', 'PCM']

        if vehicle_type_upper in both_types:
            return SuiviMode.PRISE_ET_RETOUR

        return SuiviMode.PRISE


class StatusInfo(BaseModel):
    """Status information with color coding."""
    value: str
    color: StatusColor
    days_until_expiry: Optional[int] = None


class VehicleBase(BaseModel):
    """Base vehicle model with all 19 columns from the referential."""
    dt_ul: str = Field(..., description="Délégation Territoriale ou Unité Locale")
    immat: str = Field(..., description="Immatriculation")
    indicatif: str = Field(default="", description="Code radio")
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
    suivi_mode: Optional[SuiviMode] = Field(default=None, description="Mode de suivi du véhicule")

    @field_validator('operationnel_mecanique', mode='before')
    @classmethod
    def normalize_operationnel_mecanique(cls, v: Any) -> DisponibiliteStatus:
        """Normalize operationnel_mecanique to DisponibiliteStatus enum."""
        if isinstance(v, DisponibiliteStatus):
            return v
        if isinstance(v, str):
            return DisponibiliteStatus.normalize(v)
        return DisponibiliteStatus.INDISPO

    @field_validator('suivi_mode', mode='before')
    @classmethod
    def normalize_suivi_mode(cls, v: Any) -> Optional[SuiviMode]:
        """
        Normalize suivi_mode to SuiviMode enum if a value is provided.
        """
        # If a valid value is provided, use it
        if isinstance(v, SuiviMode):
            return v
        if isinstance(v, str) and v:
            try:
                return SuiviMode(v)
            except ValueError:
                return None  # Will be set by model_validator
        return None  # Will be set by model_validator

    @model_validator(mode='after')
    def set_default_suivi_mode(self) -> 'VehicleBase':
        """
        Set default suivi_mode based on vehicle type if not already set.

        This runs after all field validators, so we can access the type field.
        """
        if self.suivi_mode is None:
            self.suivi_mode = SuiviMode.determine_from_type(self.type)
        return self


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
                "suivi_mode": "prise",
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


class VehicleCreate(BaseModel):
    """Model for creating a new vehicle."""
    dt_ul: str = Field(..., description="Délégation Territoriale ou Unité Locale")
    immat: str = Field(..., description="Immatriculation")
    indicatif: str = Field(default="", description="Code radio")
    nom_synthetique: str = Field(..., description="Nom synthétique unique (pour QR code)")
    marque: str = Field(..., description="Marque du véhicule")
    modele: str = Field(..., description="Modèle du véhicule")
    type: str = Field(..., description="Type de véhicule (VSAV, VL, VPSP, etc.)")
    date_mec: Optional[str] = Field(None, description="Date de mise en circulation (YYYY-MM-DD)")
    nb_places: str = Field(..., description="Nombre de places")
    carte_grise: str = Field(..., description="Numéro de carte grise")
    operationnel_mecanique: DisponibiliteStatus = Field(default=DisponibiliteStatus.DISPO, description="Disponibilité mécanique")
    raison_indispo: str = Field(default="", description="Raison d'indisponibilité")
    prochain_controle_technique: Optional[str] = Field(None, description="Date du prochain CT (YYYY-MM-DD)")
    prochain_controle_pollution: Optional[str] = Field(None, description="Date du prochain contrôle pollution (YYYY-MM-DD)")
    lieu_stationnement: str = Field(default="", description="Lieu de stationnement")
    instructions_recuperation: str = Field(default="", description="Lien vers instructions de récupération")
    assurance_2026: str = Field(default="", description="Informations assurance")
    numero_serie_baus: str = Field(default="", description="Numéro de série BAUS")
    commentaires: str = Field(default="", description="Commentaires libres")
    suivi_mode: Optional[SuiviMode] = Field(default=None, description="Mode de suivi du véhicule")

    @field_validator('immat', 'indicatif')
    @classmethod
    def uppercase_fields(cls, v: str) -> str:
        """Force uppercase for immat and indicatif fields."""
        return v.upper() if v else v

    class Config:
        json_schema_extra = {
            "example": {
                "dt_ul": "UL Paris 15",
                "immat": "AB-123-CD",
                "indicatif": "PARIS-15-01",
                "nom_synthetique": "VSAV-PARIS15-01",
                "marque": "Renault",
                "modele": "Master",
                "type": "VSAV",
                "date_mec": "2020-03-10",
                "nb_places": "3",
                "carte_grise": "CG123456789",
                "operationnel_mecanique": "Dispo",
                "raison_indispo": "",
                "prochain_controle_technique": "2026-08-15",
                "prochain_controle_pollution": "2026-08-15",
                "lieu_stationnement": "Garage UL Paris 15",
                "instructions_recuperation": "https://docs.google.com/document/d/...",
                "assurance_2026": "Contrat #2026-001",
                "numero_serie_baus": "BAUS-2020-001",
                "commentaires": "Véhicule principal de l'UL",
                "suivi_mode": "prise"
            }
        }


class VehicleUpdate(BaseModel):
    """Model for updating vehicle fields (all fields except immat, indicatif, nom_synthetique)."""
    # Identification
    dt_ul: Optional[str] = Field(None, description="DT ou UL du véhicule")

    # Caractéristiques
    marque: Optional[str] = Field(None, description="Marque du véhicule")
    modele: Optional[str] = Field(None, description="Modèle du véhicule")
    type: Optional[str] = Field(None, description="Type de véhicule")
    date_mec: Optional[str] = Field(None, description="Date de mise en circulation")
    nb_places: Optional[int] = Field(None, description="Nombre de places")
    carte_grise: Optional[str] = Field(None, description="Statut carte grise")

    # Disponibilité
    operationnel_mecanique: Optional[str] = Field(None, description="Statut opérationnel")
    raison_indispo: Optional[str] = Field(None, description="Raison d'indisponibilité")

    # Contrôles
    prochain_controle_technique: Optional[str] = Field(None, description="Date prochain CT")
    prochain_controle_pollution: Optional[str] = Field(None, description="Date prochain contrôle pollution")

    # Localisation & Instructions
    lieu_stationnement: Optional[str] = Field(None, description="Lieu de stationnement")
    instructions_recuperation: Optional[str] = Field(None, description="Instructions de récupération")

    # Administratif
    assurance_2026: Optional[str] = Field(None, description="Type d'assurance")
    numero_serie_baus: Optional[str] = Field(None, description="Numéro de série constructeur")
    commentaires: Optional[str] = Field(None, description="Commentaires libres")

    # Metadata CLEF
    couleur_calendrier: Optional[str] = Field(None, description="Couleur pour le calendrier (hex color)")
    suivi_mode: Optional[SuiviMode] = Field(None, description="Mode de suivi du véhicule")

    class Config:
        json_schema_extra = {
            "example": {
                "dt_ul": "DT75",
                "assurance_2026": "Tous Risques",
                "couleur_calendrier": "#FF5733",
                "commentaires": "Véhicule principal de l'UL",
                "suivi_mode": "prise"
            }
        }


class VehicleListResponse(BaseModel):
    """Response model for vehicle list endpoint."""
    count: int
    vehicles: list[Vehicle]

