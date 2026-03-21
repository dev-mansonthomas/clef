"""Tests for ReminderService."""
import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

os.environ["USE_MOCKS"] = "true"

from app.services.reminder_service import ReminderService, DEFAULT_DELAI_RAPPEL_JOURS
from app.models.repair_models import (
    DossierReparation, Devis, FournisseurSnapshot,
    StatutDossier, StatutDevis,
)
from app.models.valkey_models import DTConfiguration


def _make_devis(devis_id, statut=StatutDevis.ENVOYE, date_envoi=None, valideur_email="chef@crf.fr"):
    return Devis(
        id=devis_id,
        date_devis="2026-03-01",
        fournisseur=FournisseurSnapshot(id="f1", nom="Garage Test"),
        montant=500.0,
        statut=statut,
        valideur_email=valideur_email,
        date_envoi_approbation=date_envoi,
        cree_par="user@crf.fr",
    )


def _make_dossier(numero, immat="AB-123-CD", statut=StatutDossier.OUVERT, devis=None):
    return DossierReparation(
        numero=numero, immat=immat, dt="DT75",
        description="Test", cree_par="user@crf.fr",
        statut=statut, devis=devis or [],
    )


class TestReminderService:
    """Test ReminderService.check_overdue_devis."""

    @pytest.mark.asyncio
    async def test_no_overdue_devis(self):
        """No overdue when all devis are recent."""
        mock_valkey = AsyncMock()
        mock_valkey.get_configuration = AsyncMock(return_value=None)
        mock_valkey.list_vehicles = AsyncMock(return_value=["AB-123-CD"])
        recent_date = datetime.utcnow() - timedelta(days=1)
        dossier = _make_dossier("REP-2026-001", devis=[
            _make_devis("1", date_envoi=recent_date),
        ])
        mock_valkey.list_dossiers_reparation = AsyncMock(return_value=[dossier])

        svc = ReminderService(mock_valkey)
        result = await svc.check_overdue_devis()
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_overdue_devis_found(self):
        """Devis sent 10 days ago should be overdue with default 7-day delay."""
        mock_valkey = AsyncMock()
        mock_valkey.get_configuration = AsyncMock(return_value=None)
        mock_valkey.list_vehicles = AsyncMock(return_value=["AB-123-CD"])
        old_date = datetime.utcnow() - timedelta(days=10)
        dossier = _make_dossier("REP-2026-001", devis=[
            _make_devis("1", date_envoi=old_date),
        ])
        mock_valkey.list_dossiers_reparation = AsyncMock(return_value=[dossier])

        svc = ReminderService(mock_valkey)
        result = await svc.check_overdue_devis()
        assert len(result) == 1
        assert result[0]["devis_id"] == "1"
        assert result[0]["jours_attente"] >= 10

    @pytest.mark.asyncio
    async def test_default_delay_7_days(self):
        """Default delay should be 7 days."""
        mock_valkey = AsyncMock()
        mock_valkey.get_configuration = AsyncMock(return_value=None)

        svc = ReminderService(mock_valkey)
        delai = await svc.get_delai_rappel()
        assert delai == 7

    @pytest.mark.asyncio
    async def test_custom_delay_from_config(self):
        """Custom delay from DT configuration."""
        config = DTConfiguration(
            dt="DT75", nom="Test", gestionnaire_email="a@b.fr",
            delai_rappel_devis_jours=14,
        )
        mock_valkey = AsyncMock()
        mock_valkey.get_configuration = AsyncMock(return_value=config)

        svc = ReminderService(mock_valkey)
        delai = await svc.get_delai_rappel()
        assert delai == 14

    @pytest.mark.asyncio
    async def test_closed_dossier_ignored(self):
        """Devis in closed dossiers should not be flagged."""
        mock_valkey = AsyncMock()
        mock_valkey.get_configuration = AsyncMock(return_value=None)
        mock_valkey.list_vehicles = AsyncMock(return_value=["AB-123-CD"])
        old_date = datetime.utcnow() - timedelta(days=10)
        dossier = _make_dossier("REP-2026-001", statut=StatutDossier.CLOTURE, devis=[
            _make_devis("1", date_envoi=old_date),
        ])
        mock_valkey.list_dossiers_reparation = AsyncMock(return_value=[dossier])

        svc = ReminderService(mock_valkey)
        result = await svc.check_overdue_devis()
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_approved_devis_ignored(self):
        """Already approved devis should not be flagged."""
        mock_valkey = AsyncMock()
        mock_valkey.get_configuration = AsyncMock(return_value=None)
        mock_valkey.list_vehicles = AsyncMock(return_value=["AB-123-CD"])
        old_date = datetime.utcnow() - timedelta(days=10)
        dossier = _make_dossier("REP-2026-001", devis=[
            _make_devis("1", statut=StatutDevis.APPROUVE, date_envoi=old_date),
        ])
        mock_valkey.list_dossiers_reparation = AsyncMock(return_value=[dossier])

        svc = ReminderService(mock_valkey)
        result = await svc.check_overdue_devis()
        assert len(result) == 0

