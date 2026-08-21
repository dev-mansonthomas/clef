"""L'authentification lit les bénévoles dans Redis, plus dans Google Sheets.

Tâche **N2** de la décision **D4**, et correctif du constat **M31**.

Avant : `AuthService` appelait `sheets_service.get_benevole_by_email()`, méthode qui
n'existe **que sur le mock**. En mode réel elle levait `AttributeError`, avalée deux
fois (`auth/service.py`, puis `auth/dependencies.py` — constat M2), et **tout
utilisateur authentifié tombait à « Bénévole » sans UL ni périmètre**, sans une ligne
de log. Seul `EMAIL_GESTIONNAIRE_DT` gardait son rôle, ce chemin ne passant pas par
Sheets.

Ces tests figent le nouveau contrat : Redis est la source, et une défaillance
d'infrastructure ne se déguise plus en « utilisateur sans droits ».
"""
from typing import AsyncGenerator

import fakeredis.aioredis
import pytest
import pytest_asyncio

from app.auth.models import TokenData
from app.auth.service import AuthService
from app.models.redis_models import BenevoleData
from app.services.redis_service import RedisService


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture
async def store(redis_client) -> RedisService:
    return RedisService(redis_client=redis_client, dt="DT75")


@pytest.fixture
def service() -> AuthService:
    return AuthService()


def _token(email: str) -> TokenData:
    return TokenData(
        email=email, given_name="Prénom", family_name="Nom", sub="test-sub"
    )


async def _store_benevole(
    store: RedisService, email: str, *, responsable_ul=False, fonctions_dt=None,
    ul="UL Paris 15", statut="actif",
):
    await store.set_benevole(
        BenevoleData(
            nivol=f"NIVOL-{abs(hash(email)) % 100000}",
            dt="DT75",
            ul=ul,
            nom="Nom",
            prenom="Prénom",
            email=email,
            statut=statut,
            responsable_ul=responsable_ul,
            fonctions_dt=fonctions_dt or [],
        )
    )


@pytest.mark.asyncio
async def test_dt_manager_is_recognised_without_touching_the_datastore(service, store):
    """`EMAIL_GESTIONNAIRE_DT` est reconnu sans aucune lecture du référentiel.

    Ce chemin court-circuite le référentiel depuis toujours : c'est la seule raison
    pour laquelle le mode réel restait partiellement utilisable malgré M31.
    """
    user = await service.get_user_from_token(
        _token("thomas.manson@croix-rouge.fr"), store
    )

    assert user.role == "Gestionnaire DT"
    assert user.ul == "DT Paris"


@pytest.mark.asyncio
async def test_benevole_comes_from_redis_not_from_sheets(service, store):
    """Un bénévole présent dans Redis mais **inconnu du mock Sheets** est reconnu.

    C'est la preuve que la source a bien changé : cette adresse n'existe nulle part
    dans `app/mocks/google_sheets_mock.py`.
    """
    await _store_benevole(store, "sylvie.moreau@croix-rouge.fr")

    user = await service.get_user_from_token(
        _token("sylvie.moreau@croix-rouge.fr"), store
    )

    assert user.role == "Bénévole"
    assert user.ul == "UL Paris 15"
    assert user.dt == "DT75"


@pytest.mark.asyncio
async def test_responsable_ul_role_is_mapped(service, store):
    await _store_benevole(store, "claire.rousseau@croix-rouge.fr", responsable_ul=True)

    user = await service.get_user_from_token(
        _token("claire.rousseau@croix-rouge.fr"), store
    )

    assert user.role == "Responsable UL"
    assert user.perimetre == "UL Paris 15"
    assert user.type_perimetre == "UL"


@pytest.mark.asyncio
async def test_responsable_dt_role_is_mapped(service, store):
    await _store_benevole(
        store, "autre.gestionnaire@croix-rouge.fr", fonctions_dt=["Référent flotte"]
    )

    user = await service.get_user_from_token(
        _token("autre.gestionnaire@croix-rouge.fr"), store
    )

    assert user.role == "Gestionnaire DT"
    assert user.type_perimetre == "DT"


@pytest.mark.asyncio
async def test_email_case_does_not_prevent_recognition(service, store):
    """Le jeton peut porter une casse différente du référentiel."""
    await _store_benevole(
        store, "Claire.ROUSSEAU@croix-rouge.fr", responsable_ul=True
    )

    user = await service.get_user_from_token(
        _token("claire.rousseau@croix-rouge.fr"), store
    )

    assert user.role == "Responsable UL"


@pytest.mark.asyncio
async def test_unknown_email_gets_no_perimeter(service, store):
    """Un email absent du référentiel n'obtient aucun périmètre.

    Comportement volontairement *fail-closed* : pas de droits plutôt que des droits
    par défaut. C'est le repli existant, ici conservé et documenté.
    """
    user = await service.get_user_from_token(_token("inconnu@croix-rouge.fr"), store)

    assert user.role == "Bénévole"
    assert user.ul is None
    assert user.perimetre is None


@pytest.mark.asyncio
async def test_datastore_failure_is_not_disguised_as_a_user_without_rights(service):
    """Une panne du datastore doit **remonter**, pas se déguiser.

    C'est le cœur de M31 : l'ancienne implémentation avalait l'erreur et rendait un
    utilisateur sans périmètre, indiscernable d'un bénévole légitime. Une défaillance
    d'infrastructure doit produire un échec d'authentification (401), pas un
    utilisateur dégradé.
    """

    class BrokenStore:
        dt = "DT75"

        async def get_benevole_by_email(self, email):
            raise ConnectionError("Redis injoignable")

    with pytest.raises(ConnectionError):
        await service.get_user_from_token(
            _token("quelquun@croix-rouge.fr"), BrokenStore()
        )


def test_auth_service_no_longer_depends_on_google_sheets():
    """`auth/service.py` ne référence plus le service Sheets.

    Garde structurelle : c'est cette dépendance qui faisait dépendre le contrôle
    d'accès d'un tableur en direct, et qui ajoutait la latence de l'API Sheets à
    **chaque** requête authentifiée.
    """
    from pathlib import Path

    source = (
        Path(__file__).resolve().parent.parent / "app" / "auth" / "service.py"
    ).read_text(encoding="utf-8")

    assert "get_sheets_service" not in source
    assert "sheets_service" not in source


# ---------------------------------------------------------------------------
# Rôle dérivé et révocation — AC-9 et AC-11
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inactive_benevole_cannot_authenticate(service, store):
    """AC-9 — `statut="inactif"` révoque l'accès.

    C'est le pendant indispensable de la réconciliation : sans ce contrôle, désactiver
    un bénévole absent du référentiel ne lui retirerait rien. Le refus est signalé par
    une exception, que `get_current_user` transforme en 401 après l'avoir journalisée.
    """
    await _store_benevole(
        store, "parti@croix-rouge.fr", responsable_ul=True, statut="inactif"
    )

    with pytest.raises(PermissionError):
        await service.get_user_from_token(_token("parti@croix-rouge.fr"), store)


@pytest.mark.asyncio
async def test_dt_function_wins_over_ul_responsibility(service, store):
    """AC-11 — une fonction DT l'emporte sur la responsabilité d'UL.

    Le cas que l'ancien champ `role` ne pouvait pas représenter : la personne est les
    deux à la fois, et son périmètre effectif est le plus large.
    """
    await _store_benevole(
        store, "cumul@croix-rouge.fr",
        responsable_ul=True, fonctions_dt=["Référent flotte"],
    )

    user = await service.get_user_from_token(_token("cumul@croix-rouge.fr"), store)

    assert user.role == "Gestionnaire DT"
    assert user.type_perimetre == "DT"


@pytest.mark.asyncio
async def test_responsable_ul_perimeter_is_their_ul(service, store):
    """AC-11 — sans fonction DT, le périmètre est l'UL du bénévole."""
    await _store_benevole(
        store, "resp@croix-rouge.fr", responsable_ul=True, ul="UL Paris 20"
    )

    user = await service.get_user_from_token(_token("resp@croix-rouge.fr"), store)

    assert user.role == "Responsable UL"
    assert user.perimetre == "UL Paris 20"
    assert user.type_perimetre == "UL"


@pytest.mark.asyncio
async def test_plain_benevole_has_no_special_role(service, store):
    await _store_benevole(store, "simple@croix-rouge.fr")

    user = await service.get_user_from_token(_token("simple@croix-rouge.fr"), store)

    assert user.role == "Bénévole"
    assert user.ul == "UL Paris 15"


@pytest.mark.asyncio
async def test_dt_manager_by_email_bypasses_the_referentiel_even_if_inactive(
    service, store
):
    """`EMAIL_GESTIONNAIRE_DT` reste reconnu sans consulter le référentiel.

    Ce chemin est le filet de sécurité : il permet d'entrer dans CLEF même si le
    référentiel est vide ou en panne. Le documenter par un test, pour que personne ne
    le « corrige » en le faisant dépendre du statut.
    """
    await _store_benevole(
        store, "thomas.manson@croix-rouge.fr", statut="inactif"
    )

    user = await service.get_user_from_token(
        _token("thomas.manson@croix-rouge.fr"), store
    )

    assert user.role == "Gestionnaire DT"
