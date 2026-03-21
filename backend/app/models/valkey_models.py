"""Pydantic models for Valkey data structures."""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator


class DTConfiguration(BaseModel):
    """Configuration for a Délégation Territoriale."""
    dt: str = Field(..., description="DT identifier (e.g., 'DT75')")
    nom: str = Field(..., description="DT name")
    gestionnaire_email: str = Field(..., description="DT manager email")
    region: Optional[str] = Field(None, description="Region")
    departement: Optional[str] = Field(None, description="Department")

    # Configuration fields (migrated from ConfigService)
    sheets_url_vehicules: Optional[str] = Field(None, description="URL du référentiel véhicules (Google Sheets)")
    sheets_url_benevoles: Optional[str] = Field(None, description="URL du référentiel bénévoles (Google Sheets)")
    sheets_url_responsables: Optional[str] = Field(None, description="URL du référentiel responsables (Google Sheets)")
    template_doc_url: Optional[str] = Field(None, description="URL du template de document véhicule")
    drive_folder_id: Optional[str] = Field(None, description="Identifiant du dossier Google Drive racine de la DT")
    drive_folder_url: Optional[str] = Field(None, description="URL du dossier Google Drive racine de la DT")
    drive_vehicles_folder_id: Optional[str] = Field(None, description="Identifiant du dossier Drive 'Véhicules'")
    drive_vehicles_folder_url: Optional[str] = Field(None, description="URL du dossier Drive 'Véhicules'")
    drive_dt_folder_id: Optional[str] = Field(None, description="Identifiant du dossier Drive de la DT")
    drive_dt_folder_url: Optional[str] = Field(None, description="URL du dossier Drive de la DT")
    drive_sync_status: Optional[str] = Field("idle", description="Statut de création de l'arborescence Drive")
    drive_sync_processed: int = Field(0, description="Nombre de véhicules traités ou index courant")
    drive_sync_total: int = Field(0, description="Nombre total de véhicules à traiter")
    drive_sync_current_vehicle: Optional[str] = Field(None, description="Nom du véhicule en cours de traitement")
    drive_sync_message: Optional[str] = Field(None, description="Message de progression de la synchronisation Drive")
    drive_sync_error: Optional[str] = Field(None, description="Dernière erreur de synchronisation Drive")
    drive_sync_cancel_requested: bool = Field(False, description="Flag de demande d'annulation de la synchronisation Drive")
    email_destinataire_alertes: Optional[str] = Field(None, description="Email destinataire des alertes")
    delai_rappel_devis_jours: int = Field(default=7, description="Délai en jours avant rappel pour devis en attente d'approbation")
    api_keys: List[Dict] = Field(default_factory=list, description="API keys for this DT")
    document_folders: List[Dict] = Field(
        default_factory=lambda: [
            {"name": "Assurance", "mandatory": True},
            {"name": "Carnet de Bord - Documentation CRF", "mandatory": False},
            {"name": "Carte Grise", "mandatory": True},
            {"name": "Carte Total", "mandatory": True},
            {"name": "Commande", "mandatory": False},
            {"name": "Controle Technique", "mandatory": True},
            {"name": "Documentation Technique", "mandatory": False},
            {"name": "Factures", "mandatory": True},
            {"name": "Photos", "mandatory": False},
            {"name": "Plan d'Entretien", "mandatory": True},
            {"name": "Sinistres", "mandatory": True},
        ],
        description="Liste des types de sous-dossiers par véhicule"
    )


class VehicleData(BaseModel):
    """Vehicle data stored in Valkey - matches all 19 columns from referential."""
    # Primary keys
    immat: str = Field(..., description="License plate (immatriculation)")
    dt: str = Field(..., description="DT identifier")

    # Core fields (matching Vehicle model)
    dt_ul: str = Field(..., description="Délégation Territoriale ou Unité Locale")
    indicatif: str = Field(default="", description="Code radio")
    operationnel_mecanique: str = Field(..., description="Disponibilité mécanique (Dispo/Indispo)")
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
    suivi_mode: str = Field(default="prise", description="Mode de suivi du véhicule (prise/retour/prise_et_retour)")
    couleur_calendrier: Optional[str] = Field(None, description="Couleur du véhicule dans le calendrier")
    documents: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Associated Google Drive documents by type")
    drive_folders: Dict[str, Any] = Field(default_factory=dict, description="Cached Google Drive folders for the vehicle")

    @field_validator('immat', 'indicatif')
    @classmethod
    def uppercase_fields(cls, v: str) -> str:
        """Force uppercase for immat and indicatif fields."""
        return v.upper() if v else v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "immat": "AB-123-CD",
                "dt": "DT75",
                "dt_ul": "UL Paris 15",
                "marque": "Renault",
                "modele": "Master",
                "indicatif": "VPSU 81",
                "nom_synthetique": "vpsu-81",
                "operationnel_mecanique": "Dispo",
                "raison_indispo": "",
                "prochain_controle_technique": "2027-06-15",
                "prochain_controle_pollution": "2027-06-15",
                "type": "VSAV",
                "date_mec": "2020-03-10",
                "carte_grise": "CG123456789",
                "nb_places": "3",
                "commentaires": "Véhicule principal",
                "lieu_stationnement": "Garage UL",
                "instructions_recuperation": "https://docs.google.com/...",
                "assurance_2026": "Contrat #2026-001",
                "numero_serie_baus": "BAUS-2020-001",
                "suivi_mode": "prise",
                "documents": {
                    "carte_grise": {
                        "file_id": "drive-file-123",
                        "name": "carte-grise.pdf"
                    }
                }
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
    role: Optional[str] = Field(None, description="Role: 'responsable_ul', 'responsable_dt', or null for regular benevole")

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


class ResponsableData(BaseModel):
    """Responsable data stored in Valkey."""
    email: str = Field(..., description="Email address")
    dt: str = Field(..., description="DT identifier")
    nom: str = Field(..., description="Last name")
    prenom: str = Field(..., description="First name")
    role: str = Field(..., description="Role (e.g., 'Responsable UL', 'Gestionnaire DT')")
    perimetre: Optional[str] = Field(None, description="Scope (UL or activity)")
    type_perimetre: Optional[str] = Field(None, description="Scope type: 'DT', 'UL', 'Activité Spécialisée'")
    ul: Optional[str] = Field(None, description="UL identifier if applicable")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "responsable@croix-rouge.fr",
                "dt": "DT75",
                "nom": "Durand",
                "prenom": "Pierre",
                "role": "Responsable UL",
                "perimetre": "UL Paris 15",
                "type_perimetre": "UL",
                "ul": "UL Paris 15"
            }
        }
    )


class ResponsableVehiculeData(BaseModel):
    """Responsable véhicule data stored in Valkey."""
    email: str = Field(..., description="Email address")
    nivol: str = Field(..., description="NIVOL identifier")
    nom: str = Field(..., description="Last name")
    prenom: str = Field(..., description="First name")
    ul: str = Field(..., description="Unité Locale")
    telephone: str = Field(..., description="Phone number")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "pauline.michel@croix-rouge.fr",
                "nivol": "01100112935Y",
                "nom": "MICHEL",
                "prenom": "Pauline",
                "ul": "UNITE LOCALE DE PARIS XIII",
                "telephone": "06 81 79 53 09"
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

