"""Écriture de l'organisation : `PATCH /api/{dt}/benevoles/{email}`.

`docs/specs/synchronisation-referentiel-benevoles.md` §« Signatures attendues ».

Trois corrections par rapport à l'endpoint précédent :

1. **Il écrivait l'UL.** Nommer un responsable d'UL déplaçait le bénévole dans cette UL
   (`benevoles.py:203-205`). L'UL appartient à la feuille : la synchronisation suivante
   l'aurait de toute façon rétablie, en laissant entre-temps un état incohérent.
2. **Il parcourait toute la délégation** pour retrouver un bénévole par email. L'index
   `by_email` le fait à coût constant.
3. **Il écrivait un `role` à valeur unique**, incapable d'exprimer qu'une personne est
   responsable de son UL *et* porteuse d'une fonction DT.
"""
from typing import AsyncGenerator

import fakeredis.aioredis
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.auth.dependencies import require_dt_manager
from app.auth.models import User
from app.main import app
from app.models.redis_models import BenevoleData
from app.services.redis_dependencies import get_redis_service
from app.services.redis_service import RedisService


@pytest_asyncio.fixture
async def store() -> AsyncGenerator:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = RedisService(redis_client=client, dt="DT75")
    await service.set_benevole(BenevoleData(
        nivol="00123456A", dt="DT75", ul="UL Paris 15",
        nom="Dupont", prenom="Jean", email="jean.dupont@croix-rouge.fr",
        telephone="+33 6 11 22 33 44",
    ))
    yield service
    await client.flushdb()
    await client.aclose()


@pytest.fixture
def as_dt_manager(store):
    def _user() -> User:
        return User(
            email="thomas.manson@croix-rouge.fr", nom="Manson", prenom="Thomas",
            dt="DT75", ul="DT Paris", role="Gestionnaire DT",
            perimetre="DT Paris", type_perimetre="DT",
        )

    app.dependency_overrides[require_dt_manager] = _user
    app.dependency_overrides[get_redis_service] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


PATH = "/api/DT75/benevoles/jean.dupont@croix-rouge.fr"


@pytest.mark.asyncio
async def test_patch_sets_responsable_ul_without_touching_the_ul(as_dt_manager, store):
    """Nommer un responsable d'UL ne déplace pas le bénévole."""
    response = as_dt_manager.patch(PATH, json={"responsable_ul": True})

    assert response.status_code == 200
    benevole = await store.get_benevole("00123456A")
    assert benevole.responsable_ul is True
    assert benevole.ul == "UL Paris 15", "l'UL appartient à la feuille"


@pytest.mark.asyncio
async def test_patch_sets_dt_functions(as_dt_manager, store):
    response = as_dt_manager.patch(
        PATH, json={"fonctions_dt": ["Référent flotte", "Suppléant logistique"]}
    )

    assert response.status_code == 200
    benevole = await store.get_benevole("00123456A")
    assert benevole.fonctions_dt == ["Référent flotte", "Suppléant logistique"]


@pytest.mark.asyncio
async def test_patch_can_set_both_responsibilities(as_dt_manager, store):
    """Le cas que l'ancien `role` ne pouvait pas représenter."""
    as_dt_manager.patch(
        PATH, json={"responsable_ul": True, "fonctions_dt": ["Référent flotte"]}
    )

    benevole = await store.get_benevole("00123456A")
    assert benevole.responsable_ul is True
    assert benevole.fonctions_dt == ["Référent flotte"]


@pytest.mark.asyncio
async def test_patch_can_deactivate_and_reactivate(as_dt_manager, store):
    """Le statut est pilotable à la main : c'est le recours si la réconciliation
    désactive quelqu'un à tort."""
    as_dt_manager.patch(PATH, json={"statut": "inactif"})
    assert (await store.get_benevole("00123456A")).statut == "inactif"

    as_dt_manager.patch(PATH, json={"statut": "actif"})
    assert (await store.get_benevole("00123456A")).statut == "actif"


@pytest.mark.asyncio
async def test_patch_leaves_untouched_fields_alone(as_dt_manager, store):
    """Un champ absent de la requête n'est pas réinitialisé."""
    as_dt_manager.patch(PATH, json={"fonctions_dt": ["Référent flotte"]})
    as_dt_manager.patch(PATH, json={"responsable_ul": True})

    benevole = await store.get_benevole("00123456A")
    assert benevole.fonctions_dt == ["Référent flotte"]
    assert benevole.responsable_ul is True


def test_patch_cannot_modify_identity_fields(as_dt_manager):
    """L'identité n'est pas modifiable par cette route.

    Les champs supplémentaires sont ignorés par le modèle de requête : une tentative
    d'écrire un nom ou une UL n'a aucun effet, plutôt que d'être acceptée en silence
    puis écrasée à la synchronisation suivante.
    """
    response = as_dt_manager.patch(
        PATH, json={"nom": "Piraté", "ul": "UL Ailleurs", "email": "autre@x.fr"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["nom"] == "Dupont"
    assert body["ul"] == "UL Paris 15"


def test_patch_on_unknown_email_is_404(as_dt_manager):
    response = as_dt_manager.patch(
        "/api/DT75/benevoles/inconnu@croix-rouge.fr", json={"responsable_ul": True}
    )

    assert response.status_code == 404


def test_patch_rejects_an_invalid_statut(as_dt_manager):
    response = as_dt_manager.patch(PATH, json={"statut": "suspendu"})

    assert response.status_code == 422
