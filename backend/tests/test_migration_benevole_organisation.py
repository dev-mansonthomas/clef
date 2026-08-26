"""Migration du champ `role` vers `responsable_ul` + `fonctions_dt`.

⚠️ **À lancer avant le déploiement, pas après.** Le nouveau code lit
`responsable_ul` et `fonctions_dt` ; sur un document non migré, Pydantic leur donne
`False` et `[]` — donc **tous les responsables perdraient leurs droits** jusqu'à la
migration. Voir la section « risques » de
`docs/specs/synchronisation-referentiel-benevoles.md`.
"""
from typing import AsyncGenerator

import fakeredis.aioredis
import pytest
import pytest_asyncio

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


async def _write_legacy(client, nivol: str, role, ul="UL Paris 15", email=None):
    """Écrit un document à l'ancien format, avec `role` et sans les champs CLEF."""
    document = {
        "nivol": nivol, "dt": "DT75", "ul": ul,
        "nom": "Nom", "prenom": "Prénom",
        "email": email or f"{nivol.lower()}@croix-rouge.fr",
        "role": role,
    }
    await client.json().set(f"DT75:benevoles:{nivol}", "$", document)
    await client.sadd("DT75:benevoles:index", nivol)


@pytest.mark.asyncio
async def test_responsable_ul_becomes_the_boolean(dt75, redis_client):
    await _write_legacy(redis_client, "00111111A", "responsable_ul")

    await dt75.migrate_benevole_role_to_organisation()

    benevole = await dt75.get_benevole("00111111A")
    assert benevole.responsable_ul is True
    assert benevole.fonctions_dt == []
    assert benevole.statut == "actif"


@pytest.mark.asyncio
async def test_responsable_dt_becomes_a_dt_function(dt75, redis_client):
    await _write_legacy(redis_client, "00222222B", "responsable_dt")

    await dt75.migrate_benevole_role_to_organisation()

    benevole = await dt75.get_benevole("00222222B")
    assert benevole.fonctions_dt == ["Gestionnaire DT"]
    assert benevole.responsable_ul is False


@pytest.mark.asyncio
async def test_null_role_becomes_plain_benevole(dt75, redis_client):
    await _write_legacy(redis_client, "00333333C", None)

    await dt75.migrate_benevole_role_to_organisation()

    benevole = await dt75.get_benevole("00333333C")
    assert benevole.responsable_ul is False
    assert benevole.fonctions_dt == []


@pytest.mark.asyncio
async def test_migration_drops_the_legacy_role_field(dt75, redis_client):
    """Le champ doit disparaître du document, pas seulement être ignoré.

    Sinon une relecture par du code ancien, ou une inspection manuelle, laisserait
    croire que le rôle est encore une source de vérité.
    """
    await _write_legacy(redis_client, "00444444D", "responsable_ul")

    await dt75.migrate_benevole_role_to_organisation()

    raw = await redis_client.json().get("DT75:benevoles:00444444D")
    assert "role" not in raw


@pytest.mark.asyncio
async def test_migration_builds_the_email_index(dt75, redis_client):
    """Migrer doit aussi rendre le bénévole authentifiable.

    Les documents hérités n'ont pas d'entrée `by_email` : sans elle,
    l'authentification ne les retrouve pas.
    """
    await _write_legacy(redis_client, "00555555E", None, email="cible@croix-rouge.fr")

    await dt75.migrate_benevole_role_to_organisation()

    found = await dt75.get_benevole_by_email("cible@croix-rouge.fr")
    assert found is not None and found.nivol == "00555555E"


@pytest.mark.asyncio
async def test_migration_is_idempotent(dt75, redis_client):
    await _write_legacy(redis_client, "00666666F", "responsable_ul")

    first = await dt75.migrate_benevole_role_to_organisation()
    second = await dt75.migrate_benevole_role_to_organisation()

    benevole = await dt75.get_benevole("00666666F")
    assert benevole.responsable_ul is True
    assert first["migrated"] == 1
    assert second["already_migrated"] == 1


@pytest.mark.asyncio
async def test_migration_preserves_organisation_already_set(dt75, redis_client):
    """Une organisation déjà saisie dans CLEF n'est pas réécrite par la migration."""
    from app.models.redis_models import BenevoleData

    await dt75.set_benevole(BenevoleData(
        nivol="00777777G", dt="DT75", ul="UL Paris 15", nom="N", prenom="P",
        email="deja@croix-rouge.fr", responsable_ul=True,
        fonctions_dt=["Référent flotte"],
    ))

    await dt75.migrate_benevole_role_to_organisation()

    benevole = await dt75.get_benevole("00777777G")
    assert benevole.fonctions_dt == ["Référent flotte"]
    assert benevole.responsable_ul is True


@pytest.mark.asyncio
async def test_migration_reports_benevoles_without_ul(dt75, redis_client):
    """Les documents sans UL sont signalés, pas corrigés d'office.

    La règle « un bénévole a toujours une UL » est imposée à la synchronisation. Un
    document hérité qui y contrevient est une donnée à corriger en amont, dans la
    feuille — la migration le compte pour qu'il soit visible.
    """
    await _write_legacy(redis_client, "00888888H", None, ul=None)

    result = await dt75.migrate_benevole_role_to_organisation()

    assert result["without_ul"] == 1
