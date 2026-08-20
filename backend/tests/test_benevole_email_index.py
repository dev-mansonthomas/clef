"""Index email → bénévole, requis par l'authentification.

L'authentification identifie un utilisateur par son **email** (c'est ce que porte le
jeton Google), alors que les bénévoles sont stockés sous leur **NIVOL**
(`{dt}:benevoles:{nivol}`). Sans index, retrouver un bénévole par email imposerait de
parcourir tout l'index de la délégation et de désérialiser chaque document — sur le
chemin d'authentification, donc **à chaque requête**. D'où cet index.

Voir la tâche N2 de `docs/TODO.md` et le constat M31.
"""
from typing import AsyncGenerator

import fakeredis.aioredis
import pytest
import pytest_asyncio

from app.models.redis_models import BenevoleData
from app.services.redis_service import RedisService


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture
async def dt75(redis_client) -> RedisService:
    return RedisService(redis_client=redis_client, dt="DT75")


def _benevole(**overrides) -> BenevoleData:
    data = {
        "nivol": "00123456A",
        "dt": "DT75",
        "ul": "UL Paris 15",
        "nom": "Dupont",
        "prenom": "Jean",
        "email": "jean.dupont@croix-rouge.fr",
        "role": None,
    }
    data.update(overrides)
    return BenevoleData(**data)


@pytest.mark.asyncio
async def test_lookup_by_email_returns_the_benevole(dt75):
    """`set_benevole` rend le bénévole retrouvable par son email."""
    await dt75.set_benevole(_benevole())

    found = await dt75.get_benevole_by_email("jean.dupont@croix-rouge.fr")

    assert found is not None
    assert found.nivol == "00123456A"
    assert found.nom == "Dupont"


@pytest.mark.asyncio
async def test_lookup_by_email_is_case_insensitive(dt75):
    """La casse de l'email ne doit pas empêcher la reconnaissance.

    Le fournisseur d'identité peut renvoyer une casse différente de celle saisie dans
    le référentiel. Un utilisateur légitime non reconnu serait silencieusement
    dégradé en « Bénévole » sans périmètre (constat M31).
    """
    await dt75.set_benevole(_benevole(email="Jean.DUPONT@croix-rouge.fr"))

    assert await dt75.get_benevole_by_email("jean.dupont@croix-rouge.fr") is not None
    assert await dt75.get_benevole_by_email("JEAN.DUPONT@CROIX-ROUGE.FR") is not None


@pytest.mark.asyncio
async def test_lookup_by_unknown_email_returns_none(dt75):
    """Un email inconnu renvoie None, sans lever."""
    await dt75.set_benevole(_benevole())

    assert await dt75.get_benevole_by_email("inconnu@croix-rouge.fr") is None


@pytest.mark.asyncio
async def test_benevole_without_email_is_stored_without_index_entry(dt75):
    """`email` est optionnel sur `BenevoleData` : ne pas indexer, ne pas planter."""
    assert await dt75.set_benevole(_benevole(nivol="00999999Z", email=None))

    assert await dt75.get_benevole("00999999Z") is not None
    assert await dt75.get_benevole_by_email("") is None


@pytest.mark.asyncio
async def test_changing_the_email_drops_the_stale_index_entry(dt75):
    """Changer l'email ne doit pas laisser l'ancien utilisable.

    Sans cela, une adresse retirée du référentiel continuerait d'identifier le
    bénévole — donc d'ouvrir une session à son nom.
    """
    await dt75.set_benevole(_benevole(email="ancien@croix-rouge.fr"))
    await dt75.set_benevole(_benevole(email="nouveau@croix-rouge.fr"))

    assert await dt75.get_benevole_by_email("nouveau@croix-rouge.fr") is not None
    assert await dt75.get_benevole_by_email("ancien@croix-rouge.fr") is None


@pytest.mark.asyncio
async def test_deleting_a_benevole_drops_the_index_entry(dt75):
    """Après suppression, l'email ne doit plus identifier personne."""
    await dt75.set_benevole(_benevole())
    await dt75.delete_benevole("00123456A")

    assert await dt75.get_benevole_by_email("jean.dupont@croix-rouge.fr") is None


@pytest.mark.asyncio
async def test_index_is_scoped_to_the_delegation(redis_client):
    """L'index porte le préfixe DT, comme toute clé (ADR 0004).

    Un bénévole de DT75 ne doit pas être retrouvable via un service DT92 : c'est le
    seul mécanisme d'isolation multi-tenant, et l'authentification en dépend.
    """
    dt75 = RedisService(redis_client=redis_client, dt="DT75")
    dt92 = RedisService(redis_client=redis_client, dt="DT92")

    await dt75.set_benevole(_benevole())

    assert await dt75.get_benevole_by_email("jean.dupont@croix-rouge.fr") is not None
    assert await dt92.get_benevole_by_email("jean.dupont@croix-rouge.fr") is None


@pytest.mark.asyncio
async def test_backfill_indexes_benevoles_written_before_the_index_existed(dt75, redis_client):
    """Le backfill rattrape les bénévoles écrits avant l'existence de l'index.

    Indispensable, et pas cosmétique : l'authentification s'appuie désormais sur cet
    index. Sans rattrapage, tout bénévole déjà en base serait introuvable — donc
    ramené à « Bénévole » sans périmètre. C'est exactement le symptôme de M31 que
    cette migration évite de réintroduire par la porte des données.
    """
    # Écriture « à l'ancienne » : le document et les index historiques, sans by_email.
    legacy = _benevole(nivol="00777777X", email="legacy@croix-rouge.fr")
    await redis_client.json().set(
        "DT75:benevoles:00777777X", "$", legacy.model_dump(mode="json")
    )
    await redis_client.sadd("DT75:benevoles:index", "00777777X")

    assert await dt75.get_benevole_by_email("legacy@croix-rouge.fr") is None

    result = await dt75.backfill_benevole_email_index()

    assert result["indexed"] == 1
    found = await dt75.get_benevole_by_email("legacy@croix-rouge.fr")
    assert found is not None and found.nivol == "00777777X"


@pytest.mark.asyncio
async def test_backfill_is_idempotent_and_counts_skipped(dt75):
    """Relancer le backfill ne casse rien et ne compte pas deux fois."""
    await dt75.set_benevole(_benevole())
    await dt75.set_benevole(_benevole(nivol="00888888Y", email=None))

    first = await dt75.backfill_benevole_email_index()
    second = await dt75.backfill_benevole_email_index()

    # Le bénévole sans email est comptabilisé à part, jamais indexé.
    assert first["without_email"] == 1
    assert second["without_email"] == 1
    assert await dt75.get_benevole_by_email("jean.dupont@croix-rouge.fr") is not None
