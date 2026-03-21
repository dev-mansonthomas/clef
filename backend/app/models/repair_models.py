"""Pydantic models for repair dossiers, quotes, invoices, and suppliers."""
from typing import Optional, List
from datetime import datetime, date
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class StatutDossier(str, Enum):
    """Statut d'un dossier de réparation."""
    OUVERT = "ouvert"
    CLOTURE = "cloture"
    ANNULE = "annule"


class StatutDevis(str, Enum):
    """Statut d'un devis."""
    EN_ATTENTE = "en_attente"
    ENVOYE = "envoye"
    APPROUVE = "approuve"
    REFUSE = "refuse"
    ANNULE = "annule"


class ClassificationComptable(str, Enum):
    """Classification comptable d'une facture."""
    ENTRETIEN_COURANT = "entretien_courant"
    REPARATION_CARROSSERIE = "reparation_carrosserie"
    REPARATION_SANITAIRE = "reparation_sanitaire"
    REPARATION_MARQUAGE = "reparation_marquage"
    CONTROLE_TECHNIQUE = "controle_technique"
    FRAIS_DUPLICATA_CG = "frais_duplicata_cg"
    AUTRE = "autre"


class NiveauFournisseur(str, Enum):
    """Niveau d'un fournisseur."""
    DT = "dt"
    UL = "ul"


class ActionHistorique(str, Enum):
    """Actions tracées dans l'historique."""
    CREATION = "creation"
    MODIFICATION = "modification"
    DEVIS_AJOUTE = "devis_ajoute"
    DEVIS_MODIFIE = "devis_modifie"
    DEVIS_ANNULE = "devis_annule"
    DEVIS_ENVOYE_APPROBATION = "devis_envoye_approbation"
    DEVIS_APPROUVE = "devis_approuve"
    DEVIS_REFUSE = "devis_refuse"
    FACTURE_AJOUTEE = "facture_ajoutee"
    FACTURE_MODIFIEE = "facture_modifiee"
    CLOTURE = "cloture"
    REOUVERTURE = "reouverture"
    ANNULATION = "annulation"


class FichierDrive(BaseModel):
    """Référence vers un fichier Google Drive."""
    file_id: str = Field(..., description="Google Drive file ID")
    name: str = Field(..., description="Nom du fichier")
    web_view_link: str = Field(..., description="Lien de visualisation Google Drive")


class FournisseurSnapshot(BaseModel):
    """Snapshot d'un fournisseur embarqué dans un devis ou une facture."""
    id: str = Field(..., description="UUID du fournisseur")
    nom: str = Field(..., description="Nom du fournisseur")
    adresse: Optional[str] = Field(None, description="Adresse")
    telephone: Optional[str] = Field(None, description="Téléphone")
    siret: Optional[str] = Field(None, description="Numéro SIRET")
    email: Optional[str] = Field(None, description="Email de contact")


class Fournisseur(BaseModel):
    """Fournisseur (supplier) complet."""
    id: str = Field(..., description="UUID du fournisseur")
    nom: str = Field(..., description="Nom du fournisseur")
    adresse: Optional[str] = Field(None, description="Adresse")
    telephone: Optional[str] = Field(None, description="Téléphone")
    siret: Optional[str] = Field(None, description="Numéro SIRET")
    email: Optional[str] = Field(None, description="Email de contact")
    contact_nom: Optional[str] = Field(None, description="Nom du contact")
    specialites: List[str] = Field(default_factory=list, description="Spécialités")
    niveau: NiveauFournisseur = Field(..., description="Niveau: dt ou ul")
    ul_id: Optional[str] = Field(None, description="ID de l'UL (null si niveau=dt)")
    cree_par: str = Field(..., description="Email du créateur")
    cree_le: datetime = Field(default_factory=datetime.utcnow, description="Date de création")

    def to_snapshot(self) -> FournisseurSnapshot:
        """Convertir en snapshot pour embarquer dans un devis/facture."""
        return FournisseurSnapshot(
            id=self.id,
            nom=self.nom,
            adresse=self.adresse,
            telephone=self.telephone,
            siret=self.siret,
            email=self.email,
        )


class Devis(BaseModel):
    """Devis (quote) associé à un dossier de réparation."""
    id: str = Field(..., description="UUID du devis")
    date_devis: date = Field(..., description="Date du devis")
    fournisseur: FournisseurSnapshot = Field(..., description="Snapshot du fournisseur")
    description: Optional[str] = Field(None, description="Description des travaux")
    montant: float = Field(..., description="Montant du devis en euros TTC")
    fichier: Optional[FichierDrive] = Field(None, description="Fichier devis (PDF/image)")
    statut: StatutDevis = Field(default=StatutDevis.EN_ATTENTE, description="Statut du devis")
    valideur_email: Optional[str] = Field(None, description="Email du valideur")
    valideur_commentaire: Optional[str] = Field(None, description="Commentaire du valideur")
    token_approbation: Optional[str] = Field(None, description="Token sécurisé pour approbation")
    date_envoi_approbation: Optional[datetime] = Field(None, description="Date d'envoi pour approbation")
    date_decision: Optional[datetime] = Field(None, description="Date de la décision")
    cree_par: str = Field(..., description="Email du créateur")
    cree_le: datetime = Field(default_factory=datetime.utcnow, description="Date de création")


class Facture(BaseModel):
    """Facture (invoice) associée à un dossier de réparation."""
    id: str = Field(..., description="UUID de la facture")
    date_facture: date = Field(..., description="Date de la facture")
    fournisseur: FournisseurSnapshot = Field(..., description="Snapshot du fournisseur")
    classification: ClassificationComptable = Field(..., description="Classification comptable")
    description: Optional[str] = Field(None, description="Description des travaux")
    montant_total: float = Field(..., description="Montant total TTC en euros")
    montant_crf: float = Field(..., description="Montant à charge CRF TTC en euros")
    fichier: Optional[FichierDrive] = Field(None, description="Fichier facture (PDF/image)")
    devis_id: Optional[str] = Field(None, description="UUID du devis associé (null si aucun)")
    cree_par: str = Field(..., description="Email du créateur")
    cree_le: datetime = Field(default_factory=datetime.utcnow, description="Date de création")


class HistoriqueEntry(BaseModel):
    """Entrée d'historique / audit trail pour un dossier de réparation."""
    date: datetime = Field(default_factory=datetime.utcnow, description="Date de l'action")
    auteur: str = Field(..., description="Email de l'auteur")
    action: ActionHistorique = Field(..., description="Type d'action")
    details: str = Field(..., description="Description de l'action")
    ref: str = Field(..., description="Clé Valkey de l'objet concerné")


class DossierReparation(BaseModel):
    """Dossier de réparation véhicule."""
    numero: str = Field(..., description="Numéro du dossier (ex: REP-2026-001)")
    immat: str = Field(..., description="Immatriculation du véhicule")
    dt: str = Field(..., description="Identifiant DT")
    description: str = Field(..., description="Description des travaux")
    photos: List[FichierDrive] = Field(default_factory=list, description="Photos associées")
    sinistre_id: Optional[str] = Field(None, description="ID du sinistre lié (futur)")
    statut: StatutDossier = Field(default=StatutDossier.OUVERT, description="Statut du dossier")
    cree_par: str = Field(..., description="Email du créateur")
    cree_le: datetime = Field(default_factory=datetime.utcnow, description="Date de création")
    cloture_le: Optional[datetime] = Field(None, description="Date de clôture")
    devis: List[Devis] = Field(default_factory=list, description="Devis associés")
    factures: List[Facture] = Field(default_factory=list, description="Factures associées")




# ========== Request / Response models for API ==========


class DossierReparationCreate(BaseModel):
    """Request body for creating a new dossier de réparation."""
    description: str = Field(..., min_length=1, description="Description des travaux")


class DossierReparationUpdate(BaseModel):
    """Request body for updating a dossier de réparation (description, close, reopen, cancel)."""
    description: Optional[str] = Field(None, description="Nouvelle description")
    statut: Optional[StatutDossier] = Field(None, description="Nouveau statut (cloture, ouvert, annule)")


class DossierReparationListResponse(BaseModel):
    """Response for listing dossiers de réparation."""
    count: int = Field(..., description="Nombre de dossiers")
    dossiers: List[DossierReparation] = Field(default_factory=list, description="Liste des dossiers")



class FournisseurCreate(BaseModel):
    """Request body for creating a new fournisseur."""
    nom: str = Field(..., min_length=1, description="Nom du fournisseur")
    adresse: Optional[str] = Field(None, description="Adresse")
    telephone: Optional[str] = Field(None, description="Téléphone")
    siret: Optional[str] = Field(None, description="Numéro SIRET")
    email: Optional[str] = Field(None, description="Email de contact")
    contact_nom: Optional[str] = Field(None, description="Nom du contact")
    specialites: List[str] = Field(default_factory=list, description="Spécialités")
    niveau: NiveauFournisseur = Field(..., description="Niveau: dt ou ul")
    ul_id: Optional[str] = Field(None, description="ID de l'UL (requis si niveau=ul)")


class FournisseurUpdate(BaseModel):
    """Request body for updating a fournisseur."""
    nom: Optional[str] = Field(None, min_length=1, description="Nom du fournisseur")
    adresse: Optional[str] = Field(None, description="Adresse")
    telephone: Optional[str] = Field(None, description="Téléphone")
    siret: Optional[str] = Field(None, description="Numéro SIRET")
    email: Optional[str] = Field(None, description="Email de contact")
    contact_nom: Optional[str] = Field(None, description="Nom du contact")
    specialites: Optional[List[str]] = Field(None, description="Spécialités")


class FournisseurListResponse(BaseModel):
    """Response for listing fournisseurs."""
    count: int = Field(..., description="Nombre de fournisseurs")
    fournisseurs: List[Fournisseur] = Field(default_factory=list, description="Liste des fournisseurs")


# ========== Devis request/response models ==========


class DevisCreate(BaseModel):
    """Request body for creating a new devis."""
    date_devis: date = Field(..., description="Date du devis")
    fournisseur_id: str = Field(..., description="UUID du fournisseur")
    fournisseur_nom: str = Field(..., description="Nom du fournisseur")
    description_travaux: Optional[str] = Field(None, description="Description des travaux")
    montant: float = Field(..., gt=0, description="Montant du devis en euros TTC")


class DevisUpdate(BaseModel):
    """Request body for updating a devis (status change)."""
    statut: StatutDevis = Field(..., description="Nouveau statut du devis")


# ========== Facture request/response models ==========


class FactureCreate(BaseModel):
    """Request body for creating a new facture."""
    date_facture: date = Field(..., description="Date de la facture")
    fournisseur_id: str = Field(..., description="UUID du fournisseur")
    fournisseur_nom: str = Field(..., description="Nom du fournisseur")
    classification: ClassificationComptable = Field(..., description="Classification comptable")
    description_travaux: Optional[str] = Field(None, description="Description des travaux")
    montant_total: float = Field(..., gt=0, description="Montant total TTC en euros")
    montant_crf: float = Field(..., gt=0, description="Montant à charge CRF TTC en euros")
    devis_id: Optional[str] = Field(None, description="UUID du devis associé (optionnel)")


class FactureResponse(BaseModel):
    """Response for facture creation with optional warnings."""
    facture: Facture = Field(..., description="La facture créée")
    warning_no_devis: bool = Field(default=False, description="Aucun devis approuvé trouvé")
    warning_devis_not_approved: bool = Field(default=False, description="Le devis référencé n'est pas approuvé")
    warning_ecart: bool = Field(default=False, description="Écart > 20% entre devis et facture")
    ecart_pourcentage: Optional[float] = Field(None, description="Pourcentage d'écart devis/facture")
