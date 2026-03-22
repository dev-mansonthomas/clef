"""Service for checking overdue devis reminders."""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from app.services.valkey_service import ValkeyService
from app.models.repair_models import StatutDevis

logger = logging.getLogger(__name__)

DEFAULT_DELAI_RAPPEL_JOURS = 7


class ReminderService:
    """Scans dossiers to find overdue devis awaiting approval."""

    def __init__(self, valkey: ValkeyService):
        self.valkey = valkey

    async def get_delai_rappel(self) -> int:
        """Get configured reminder delay in days, defaults to 7."""
        config = await self.valkey.get_configuration()
        if config and hasattr(config, "delai_rappel_devis_jours"):
            return config.delai_rappel_devis_jours
        return DEFAULT_DELAI_RAPPEL_JOURS

    async def check_overdue_devis(self) -> List[Dict[str, Any]]:
        """
        Scan all dossiers for the DT, find devis with status 'envoye'
        that are older than the configured delay.

        Returns:
            List of overdue devis info dicts.
        """
        delai = await self.get_delai_rappel()
        cutoff = datetime.utcnow() - timedelta(days=delai)
        overdue: List[Dict[str, Any]] = []

        # Get all vehicles
        vehicle_immats = await self.valkey.list_vehicles()

        for immat in vehicle_immats:
            dossiers = await self.valkey.list_dossiers_reparation(immat)
            for dossier in dossiers:
                if dossier.statut.value != "ouvert":
                    continue
                for devis in dossier.devis:
                    if devis.statut != StatutDevis.ENVOYE:
                        continue
                    # Check if send date is older than cutoff
                    send_date = devis.date_envoi_approbation
                    if send_date and send_date < cutoff:
                        overdue.append({
                            "immat": immat,
                            "numero_dossier": dossier.numero,
                            "devis_id": devis.id,
                            "fournisseur": devis.fournisseur.nom,
                            "montant": devis.montant,
                            "valideur_email": devis.valideur_email,
                            "date_envoi": send_date.isoformat(),
                            "jours_attente": (datetime.utcnow() - send_date).days,
                            "description_dossier": dossier.description,
                        })

        logger.info(
            f"Reminder check for {self.valkey.dt}: "
            f"{len(overdue)} overdue devis found (delay={delai} days)"
        )
        return overdue

