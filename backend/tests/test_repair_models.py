"""Tests for repair models and RedisService CRUD operations."""
import pytest
import pytest_asyncio
from datetime import datetime, date
from typing import AsyncGenerator
import fakeredis.aioredis

from app.services.redis_service import RedisService
from app.models.repair_models import (
    DossierReparation, Devis, Facture, Fournisseur, HistoriqueEntry,
    FichierDrive, FournisseurSnapshot,
    StatutDossier, StatutDevis, ClassificationComptable,
    NiveauFournisseur, ActionHistorique,
)


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator:
    """Create a fake Redis client for testing."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture
async def redis_store(redis_client) -> RedisService:
    """Create RedisService for DT75."""
    return RedisService(redis_client=redis_client, dt="DT75")


# ========== Model Unit Tests ==========


class TestRepairModels:
    """Test Pydantic model creation and validation."""

    def test_dossier_reparation_defaults(self):
        d = DossierReparation(
            numero="REP-2026-001", immat="AB-123-CD", dt="DT75",
            description=["Test repair"], cree_par="user@croix-rouge.fr",
        )
        assert d.statut == StatutDossier.OUVERT
        assert d.devis == []
        assert d.factures == []
        assert d.photos == []
        assert d.sinistre_id is None
        assert d.cloture_le is None
        assert d.commentaire is None

    def test_devis_defaults(self):
        snap = FournisseurSnapshot(id="f1", nom="Garage Test")
        d = Devis(
            id="d1", date_devis=date(2026, 3, 20),
            fournisseur=snap, montant=450.0,
            cree_par="user@croix-rouge.fr",
        )
        assert d.statut == StatutDevis.EN_ATTENTE
        assert d.fichier is None
        assert d.valideur_email is None

    def test_facture_creation(self):
        snap = FournisseurSnapshot(id="f1", nom="Garage Test")
        f = Facture(
            id="inv1", date_facture=date(2026, 4, 15),
            fournisseur=snap,
            classification=ClassificationComptable.REPARATION_CARROSSERIE,
            montant_total=520.0, montant_crf=520.0,
            cree_par="user@croix-rouge.fr",
        )
        assert f.devis_id is None
        assert f.classification == ClassificationComptable.REPARATION_CARROSSERIE

    def test_fournisseur_to_snapshot(self):
        f = Fournisseur(
            id="f1", nom="Garage Dupont", adresse="12 rue de la Paix",
            telephone="01 23 45 67 89", siret="123456789",
            email="contact@garage.fr", niveau=NiveauFournisseur.DT,
            cree_par="user@croix-rouge.fr",
        )
        snap = f.to_snapshot()
        assert snap.id == "f1"
        assert snap.nom == "Garage Dupont"
        assert snap.adresse == "12 rue de la Paix"

    def test_fichier_drive(self):
        f = FichierDrive(file_id="abc", name="photo.jpg", web_view_link="https://drive.google.com/abc")
        assert f.file_id == "abc"

    def test_classification_comptable_values(self):
        assert len(ClassificationComptable) == 7

    def test_statut_dossier_values(self):
        assert set(s.value for s in StatutDossier) == {"ouvert", "cloture", "annule"}

    def test_statut_devis_values(self):
        assert set(s.value for s in StatutDevis) == {"en_attente", "envoye", "approuve", "refuse", "annule"}


# ========== CRUD Tests ==========


class TestDossierReparationCRUD:
    """Test dossier réparation CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_dossier(self, redis_store):
        dossier = await redis_store.create_dossier_reparation(
            immat="AB-123-CD", description=["Brake repair"],
            cree_par="user@croix-rouge.fr",
        )
        assert dossier.numero == "REP-2026-001"
        assert dossier.immat == "AB-123-CD"
        assert dossier.statut == StatutDossier.OUVERT

    @pytest.mark.asyncio
    async def test_create_dossier_auto_increment(self, redis_store):
        d1 = await redis_store.create_dossier_reparation(
            immat="AB-123-CD", description=["First"], cree_par="u@crf.fr",
        )
        d2 = await redis_store.create_dossier_reparation(
            immat="AB-123-CD", description=["Second"], cree_par="u@crf.fr",
        )
        assert d1.numero == "REP-2026-001"
        assert d2.numero == "REP-2026-002"

    @pytest.mark.asyncio
    async def test_get_dossier(self, redis_store):
        created = await redis_store.create_dossier_reparation(
            immat="AB-123-CD", description=["Test"], cree_par="u@crf.fr",
        )
        retrieved = await redis_store.get_dossier_reparation("AB-123-CD", created.numero)
        assert retrieved is not None
        assert retrieved.numero == created.numero
        assert retrieved.description == ["Test"]

    @pytest.mark.asyncio
    async def test_get_dossier_not_found(self, redis_store):
        result = await redis_store.get_dossier_reparation("XX-000-XX", "REP-2026-999")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_dossiers(self, redis_store):
        await redis_store.create_dossier_reparation(
            immat="AB-123-CD", description=["First"], cree_par="u@crf.fr",
        )
        await redis_store.create_dossier_reparation(
            immat="AB-123-CD", description=["Second"], cree_par="u@crf.fr",
        )
        dossiers = await redis_store.list_dossiers_reparation("AB-123-CD")
        assert len(dossiers) == 2


class TestHistoriqueCRUD:
    """Test historique CRUD operations."""

    @pytest.mark.asyncio
    async def test_historique_created_on_dossier_creation(self, redis_store):
        dossier = await redis_store.create_dossier_reparation(
            immat="AB-123-CD", description=["Test"], cree_par="u@crf.fr",
        )
        entries = await redis_store.get_historique("AB-123-CD", dossier.numero)
        assert len(entries) == 1
        assert entries[0].action == ActionHistorique.CREATION
        assert entries[0].auteur == "u@crf.fr"

    @pytest.mark.asyncio
    async def test_add_historique_entry(self, redis_store):
        dossier = await redis_store.create_dossier_reparation(
            immat="AB-123-CD", description=["Test"], cree_par="u@crf.fr",
        )
        entry = HistoriqueEntry(
            auteur="u@crf.fr",
            action=ActionHistorique.DEVIS_AJOUTE,
            details="Devis #1 - Garage Martin - 850€",
            ref=f"DT75:vehicules:AB-123-CD:travaux:{dossier.numero}:devis:1",
        )
        success = await redis_store.add_historique_entry("AB-123-CD", dossier.numero, entry)
        assert success is True

        entries = await redis_store.get_historique("AB-123-CD", dossier.numero)
        assert len(entries) == 2  # creation + devis_ajoute

    @pytest.mark.asyncio
    async def test_get_historique_empty(self, redis_store):
        entries = await redis_store.get_historique("XX-000-XX", "REP-2026-999")
        assert entries == []


class TestFournisseurCRUD:
    """Test fournisseur CRUD operations."""

    @pytest.mark.asyncio
    async def test_set_and_get_fournisseur_dt(self, redis_store):
        f = Fournisseur(
            id="f1", nom="Garage Dupont",
            niveau=NiveauFournisseur.DT,
            cree_par="u@crf.fr",
        )
        success = await redis_store.set_fournisseur(f)
        assert success is True

        retrieved = await redis_store.get_fournisseur("f1")
        assert retrieved is not None
        assert retrieved.nom == "Garage Dupont"
        assert retrieved.niveau == NiveauFournisseur.DT

    @pytest.mark.asyncio
    async def test_set_and_get_fournisseur_ul(self, redis_store):
        f = Fournisseur(
            id="f2", nom="Garage Local",
            niveau=NiveauFournisseur.UL, ul_id="paris-15",
            cree_par="u@crf.fr",
        )
        success = await redis_store.set_fournisseur(f)
        assert success is True

        retrieved = await redis_store.get_fournisseur("f2", ul_id="paris-15")
        assert retrieved is not None
        assert retrieved.nom == "Garage Local"
        assert retrieved.niveau == NiveauFournisseur.UL

    @pytest.mark.asyncio
    async def test_list_fournisseurs_dt(self, redis_store):
        f1 = Fournisseur(id="f1", nom="Garage A", niveau=NiveauFournisseur.DT, cree_par="u@crf.fr")
        f2 = Fournisseur(id="f2", nom="Garage B", niveau=NiveauFournisseur.DT, cree_par="u@crf.fr")
        await redis_store.set_fournisseur(f1)
        await redis_store.set_fournisseur(f2)

        result = await redis_store.list_fournisseurs_dt()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_fournisseurs_ul(self, redis_store):
        f = Fournisseur(
            id="f3", nom="Garage UL",
            niveau=NiveauFournisseur.UL, ul_id="paris-15",
            cree_par="u@crf.fr",
        )
        await redis_store.set_fournisseur(f)

        result = await redis_store.list_fournisseurs_ul("paris-15")
        assert len(result) == 1
        assert result[0].nom == "Garage UL"

        # Different UL should be empty
        result_other = await redis_store.list_fournisseurs_ul("paris-16")
        assert len(result_other) == 0

    @pytest.mark.asyncio
    async def test_list_fournisseurs_combined(self, redis_store):
        """Test listing DT + UL suppliers together."""
        f_dt = Fournisseur(id="f1", nom="DT Garage", niveau=NiveauFournisseur.DT, cree_par="u@crf.fr")
        f_ul = Fournisseur(
            id="f2", nom="UL Garage",
            niveau=NiveauFournisseur.UL, ul_id="paris-15",
            cree_par="u@crf.fr",
        )
        await redis_store.set_fournisseur(f_dt)
        await redis_store.set_fournisseur(f_ul)

        # With UL: should see both
        combined = await redis_store.list_fournisseurs(ul_id="paris-15")
        assert len(combined) == 2

        # Without UL: should see only DT
        dt_only = await redis_store.list_fournisseurs()
        assert len(dt_only) == 1
        assert dt_only[0].nom == "DT Garage"

    @pytest.mark.asyncio
    async def test_get_fournisseur_not_found(self, redis_store):
        result = await redis_store.get_fournisseur("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_multi_tenant_isolation_fournisseurs(self, redis_client):
        """Test that fournisseurs are isolated between DTs."""
        redis_75 = RedisService(redis_client=redis_client, dt="DT75")
        redis_92 = RedisService(redis_client=redis_client, dt="DT92")

        f75 = Fournisseur(id="f1", nom="Paris Garage", niveau=NiveauFournisseur.DT, cree_par="u@crf.fr")
        f92 = Fournisseur(id="f2", nom="Nanterre Garage", niveau=NiveauFournisseur.DT, cree_par="u@crf.fr")

        await redis_75.set_fournisseur(f75)
        await redis_92.set_fournisseur(f92)

        dt75_list = await redis_75.list_fournisseurs_dt()
        dt92_list = await redis_92.list_fournisseurs_dt()

        assert len(dt75_list) == 1
        assert dt75_list[0].nom == "Paris Garage"
        assert len(dt92_list) == 1
        assert dt92_list[0].nom == "Nanterre Garage"

