"""Fusion et réconciliation de la synchronisation du référentiel bénévoles.

`docs/specs/synchronisation-referentiel-benevoles.md`, critères AC-1 à AC-6 et AC-12.

Deux propriétés à tenir, et elles tirent en sens opposé :

- **Fusionner** : la feuille écrase l'identité, mais ne doit jamais toucher à
  l'organisation saisie dans CLEF (statut, responsabilité d'UL, fonctions DT).
- **Réconcilier** : le lot est un instantané complet de la délégation, donc une
  absence est significative — elle doit révoquer l'accès.

La réconciliation est la seule opération du chantier qui retire un accès **en masse**.
D'où le garde-fou de ratio, et le traitement à part du lot vide : une lecture de
feuille tronquée est le mode de panne le plus probable.
"""
from typing import AsyncGenerator

import fakeredis.aioredis
import pytest
import pytest_asyncio

from app.models.redis_models import BenevoleData
from app.services.redis_service import BenevoleIdentite, RedisService


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture
async def dt75(redis_client) -> RedisService:
    return RedisService(redis_client=redis_client, dt="DT75")


def _identite(nivol="00123456A", **overrides) -> BenevoleIdentite:
    data = {
        "nivol": nivol,
        "nom": "Dupont",
        "prenom": "Jean",
        "ul": "UL Paris 15",
        "email": f"{nivol.lower()}@croix-rouge.fr",
        "telephone": "+33 6 12 34 56 78",
    }
    data.update(overrides)
    return BenevoleIdentite(**data)


# ---------------------------------------------------------------------------
# Fusion
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_identity_is_updated_and_organisation_preserved(dt75):
    """AC-1 — la feuille écrase l'identité, CLEF garde l'organisation."""
    await dt75.set_benevole(BenevoleData(
        nivol="00123456A", dt="DT75", ul="UL Paris 15", nom="Dupont", prenom="Jean",
        email="jean.dupont@croix-rouge.fr", statut="actif",
        responsable_ul=True, fonctions_dt=["Référent flotte"],
    ))

    outcome = await dt75.upsert_benevole_identite(
        _identite(nom="Dupont-Martin", ul="UL Paris 20",
                  email="jean.dupont@croix-rouge.fr")
    )

    benevole = await dt75.get_benevole("00123456A")
    assert outcome == "updated"
    # Identité : mise à jour
    assert benevole.nom == "Dupont-Martin"
    assert benevole.ul == "UL Paris 20"
    # Organisation : intacte
    assert benevole.responsable_ul is True
    assert benevole.fonctions_dt == ["Référent flotte"]
    assert benevole.statut == "actif"


@pytest.mark.asyncio
async def test_new_benevole_gets_default_organisation(dt75):
    """AC-2 — une création n'invente aucune responsabilité."""
    outcome = await dt75.upsert_benevole_identite(_identite(nivol="00999999Z"))

    benevole = await dt75.get_benevole("00999999Z")
    assert outcome == "created"
    assert benevole.statut == "actif"
    assert benevole.responsable_ul is False
    assert benevole.fonctions_dt == []
    assert benevole.telephone == "+33 6 12 34 56 78"


@pytest.mark.asyncio
async def test_ul_change_moves_the_by_ul_index(dt75, redis_client):
    """Le nivol doit quitter l'ancienne UL.

    `set_benevole` ne faisait qu'un `sadd` sur la nouvelle : l'ancienne UL gardait une
    entrée fantôme, donc `list_benevoles(ul=...)` renvoyait un bénévole qui n'y est
    plus. Bug préexistant, corrigé ici.
    """
    await dt75.upsert_benevole_identite(_identite(ul="UL Paris 15"))
    await dt75.upsert_benevole_identite(_identite(ul="UL Paris 20"))

    assert "00123456A" not in await dt75.list_benevoles(ul="UL Paris 15")
    assert "00123456A" in await dt75.list_benevoles(ul="UL Paris 20")


@pytest.mark.asyncio
async def test_email_change_drops_the_stale_index_entry(dt75):
    """Non-régression : l'ancienne adresse ne doit plus ouvrir de session."""
    await dt75.upsert_benevole_identite(_identite(email="ancien@croix-rouge.fr"))
    await dt75.upsert_benevole_identite(_identite(email="nouveau@croix-rouge.fr"))

    assert await dt75.get_benevole_by_email("nouveau@croix-rouge.fr") is not None
    assert await dt75.get_benevole_by_email("ancien@croix-rouge.fr") is None


# ---------------------------------------------------------------------------
# Réconciliation
# ---------------------------------------------------------------------------

async def _populate(store: RedisService, count: int) -> list[str]:
    nivols = [f"NIV{i:05d}" for i in range(count)]
    for nivol in nivols:
        await store.upsert_benevole_identite(_identite(nivol=nivol))
    return nivols


@pytest.mark.asyncio
async def test_absent_benevole_is_deactivated_not_deleted(dt75):
    """AC-3 — l'accès est révoqué, l'historique préservé.

    Les entrées de carnet de bord et les réservations référencent le bénévole :
    supprimer le document casserait ces références.
    """
    nivols = await _populate(dt75, 10)
    present = set(nivols[:-1])

    result = await dt75.deactivate_benevoles_absent_from(present, max_ratio=0.2)

    absent = nivols[-1]
    benevole = await dt75.get_benevole(absent)
    assert result["deactivated"] == 1
    assert benevole is not None, "le document doit subsister"
    assert benevole.statut == "inactif"


@pytest.mark.asyncio
async def test_reappearing_benevole_is_reactivated_keeping_functions(dt75):
    """AC-4 — un retour réactive sans perdre les fonctions saisies dans CLEF."""
    await dt75.set_benevole(BenevoleData(
        nivol="00123456A", dt="DT75", ul="UL Paris 15", nom="Dupont", prenom="Jean",
        email="jean.dupont@croix-rouge.fr", statut="inactif",
        responsable_ul=True, fonctions_dt=["Référent flotte"],
    ))

    outcome = await dt75.upsert_benevole_identite(
        _identite(email="jean.dupont@croix-rouge.fr")
    )

    benevole = await dt75.get_benevole("00123456A")
    assert outcome == "reactivated"
    assert benevole.statut == "actif"
    assert benevole.responsable_ul is True
    assert benevole.fonctions_dt == ["Référent flotte"]


@pytest.mark.asyncio
async def test_deactivation_aborts_beyond_ratio(dt75):
    """AC-5 — un lot suspect n'emporte pas la délégation.

    Onglet tronqué, filtre resté actif, lecture Sheets partielle sur quota : le
    résultat serait une révocation massive de bénévoles en règle. La réconciliation
    s'abstient, et le dit.
    """
    nivols = await _populate(dt75, 10)
    present = set(nivols[:5])  # 5 sur 10 → ratio 0,5

    result = await dt75.deactivate_benevoles_absent_from(present, max_ratio=0.2)

    assert result["skipped"] is True
    assert "ratio" in result["reason"].lower()
    assert result["deactivated"] == 0
    for nivol in nivols:
        assert (await dt75.get_benevole(nivol)).statut == "actif"


@pytest.mark.asyncio
async def test_empty_batch_deactivates_nobody(dt75):
    """AC-6 — cas particulier du précédent, testé à part.

    C'est le mode de panne le plus probable d'une lecture de feuille : un lot vide ne
    doit jamais être interprété comme « plus aucun bénévole dans le département ».
    """
    nivols = await _populate(dt75, 3)

    result = await dt75.deactivate_benevoles_absent_from(set(), max_ratio=1.0)

    assert result["skipped"] is True
    for nivol in nivols:
        assert (await dt75.get_benevole(nivol)).statut == "actif"


@pytest.mark.asyncio
async def test_deactivation_within_ratio_proceeds(dt75):
    """Le garde-fou ne doit pas bloquer une réconciliation normale."""
    nivols = await _populate(dt75, 20)
    present = set(nivols[:18])  # 2 sur 20 → ratio 0,1

    result = await dt75.deactivate_benevoles_absent_from(present, max_ratio=0.2)

    assert result["skipped"] is False
    assert result["deactivated"] == 2


@pytest.mark.asyncio
async def test_already_inactive_are_not_counted_again(dt75):
    """Le ratio se calcule sur les **actifs**, et la seconde passe ne fait rien."""
    nivols = await _populate(dt75, 10)
    present = set(nivols[:9])

    first = await dt75.deactivate_benevoles_absent_from(present, max_ratio=0.2)
    second = await dt75.deactivate_benevoles_absent_from(present, max_ratio=0.2)

    assert first["deactivated"] == 1
    assert second["deactivated"] == 0
    assert second["skipped"] is False


@pytest.mark.asyncio
async def test_two_consecutive_runs_are_idempotent(dt75):
    """AC-12 — rejouer le même lot ne change rien et ne révoque personne."""
    identites = [_identite(nivol=f"NIV{i:05d}") for i in range(5)]

    for identite in identites:
        await dt75.upsert_benevole_identite(identite)
    present = {i.nivol for i in identites}
    await dt75.deactivate_benevoles_absent_from(present, max_ratio=0.2)

    outcomes = [await dt75.upsert_benevole_identite(i) for i in identites]
    result = await dt75.deactivate_benevoles_absent_from(present, max_ratio=0.2)

    assert set(outcomes) == {"updated"}
    assert result["deactivated"] == 0
    for identite in identites:
        assert (await dt75.get_benevole(identite.nivol)).statut == "actif"
