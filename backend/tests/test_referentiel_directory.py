"""L'annuaire des bénévoles n'est plus public — correctif du constat C1.

Avant : `main.py` déclarait trois routes de référentiel **en ligne**, donc sans passer
par aucun router ni aucun guard (`grep -c Depends app/main.py` → 0). `GET /api/benevoles`
répondait 200 à n'importe qui, sans cookie ni clé, et servait nom, prénom, email et UL
de tous les bénévoles — lus directement dans Google Sheets. Enjeu RGPD direct.

La route est **conservée** car les formulaires de réservation des deux applications
l'utilisent pour leur sélecteur de chauffeur ; elle est désormais authentifiée,
cadrée sur la délégation de l'appelant, et lit Redis.

Les deux autres routes (`/api/benevoles/{email}` et `/api/responsables`) n'avaient
aucun appelant — ni frontend, ni Apps Script — et sont supprimées.
"""
import os
from pathlib import Path

import fakeredis.aioredis
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

os.environ["USE_MOCKS"] = "true"

from app.auth.config import auth_settings  # noqa: E402
from app.auth.dependencies import require_authenticated_user  # noqa: E402
from app.auth.models import User  # noqa: E402
from app.main import app  # noqa: E402
from app.models.redis_models import BenevoleData  # noqa: E402
from app.services.redis_dependencies import get_redis_service  # noqa: E402
from app.services.redis_service import RedisService  # noqa: E402

auth_settings.use_mocks = True


@pytest_asyncio.fixture
async def store():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = RedisService(redis_client=client, dt="DT75")
    await service.set_benevole(BenevoleData(
        nivol="00111111A", dt="DT75", ul="UL Paris 15",
        nom="Dupont", prenom="Jean", email="jean.dupont@croix-rouge.fr", role=None,
    ))
    await service.set_benevole(BenevoleData(
        nivol="00222222B", dt="DT75", ul="UL Paris 20",
        nom="Rousseau", prenom="Claire", email="claire.rousseau@croix-rouge.fr",
        role="responsable_ul",
    ))
    # Bénévole d'une autre délégation : ne doit jamais apparaître.
    other = RedisService(redis_client=client, dt="DT92")
    await other.set_benevole(BenevoleData(
        nivol="00333333C", dt="DT92", ul="UL Nanterre",
        nom="Etranger", prenom="Autre", email="autre@croix-rouge.fr", role=None,
    ))
    yield service
    await client.flushdb()
    await client.aclose()


@pytest.fixture
def as_benevole(store):
    """Client authentifié en simple « Bénévole » — le cas de l'app terrain."""
    def _user() -> User:
        return User(
            email="jean.dupont@croix-rouge.fr", nom="Dupont", prenom="Jean",
            dt="DT75", ul="UL Paris 15", role="Bénévole",
            perimetre="UL Paris 15", type_perimetre="UL",
        )

    app.dependency_overrides[require_authenticated_user] = _user
    app.dependency_overrides[get_redis_service] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_directory_requires_authentication():
    """Sans session, l'annuaire répond 401 — c'est le cœur du correctif C1."""
    app.dependency_overrides.clear()
    response = TestClient(app).get("/api/benevoles")

    assert response.status_code == 401


def test_a_plain_benevole_can_list_the_directory(as_benevole):
    """Un bénévole sans rôle particulier y accède.

    Nécessaire : le formulaire de réservation de l'app terrain, utilisé par les
    bénévoles, a besoin de ce sélecteur de chauffeur. Restreindre aux gestionnaires
    casserait ce parcours.
    """
    response = as_benevole.get("/api/benevoles")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    emails = {b["email"] for b in body["benevoles"]}
    assert emails == {
        "jean.dupont@croix-rouge.fr",
        "claire.rousseau@croix-rouge.fr",
    }


def test_directory_is_scoped_to_the_callers_delegation(as_benevole):
    """Aucun bénévole d'une autre délégation n'est renvoyé.

    Le périmètre vient de `current_user.dt`, jamais d'un paramètre d'URL : c'est ce
    qui met cette route hors d'atteinte de la classe de faille C3.
    """
    body = as_benevole.get("/api/benevoles").json()

    assert all(b["email"] != "autre@croix-rouge.fr" for b in body["benevoles"])


def test_response_shape_matches_what_the_frontends_consume(as_benevole):
    """Les sélecteurs lisent nivol, nom, prénom, email et ul.

    `form/.../reservation-form.component.ts` utilise nivol/nom/prenom ;
    `admin/.../reservation-form.component.ts` filtre aussi sur l'email. Le contrat
    est donc figé ici pour éviter une régression silencieuse du sélecteur.
    """
    body = as_benevole.get("/api/benevoles").json()
    benevole = next(b for b in body["benevoles"] if b["nivol"] == "00111111A")

    assert benevole["nom"] == "Dupont"
    assert benevole["prenom"] == "Jean"
    assert benevole["ul"] == "UL Paris 15"
    assert benevole["email"] == "jean.dupont@croix-rouge.fr"


@pytest.mark.parametrize(
    "path",
    ["/api/benevoles/jean.dupont@croix-rouge.fr", "/api/responsables"],
)
def test_unused_public_routes_are_gone(path):
    """Les deux routes sans appelant sont supprimées, pas seulement gardées.

    Aucun frontend ni Apps Script ne les appelait : la surface d'exposition la plus
    sûre est celle qui n'existe pas.
    """
    app.dependency_overrides.clear()
    assert TestClient(app).get(path).status_code == 404


def test_main_declares_no_referential_route():
    """`main.py` ne déclare plus aucune route de référentiel.

    Garde structurelle : ce fichier n'a pas de `Depends`, donc toute route qui y est
    déclarée est publique par construction. Y ajouter une route servant des données
    personnelles reproduirait C1 à l'identique.
    """
    source = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text(
        encoding="utf-8"
    )

    for leaked in ('"/api/benevoles"', '"/api/benevoles/{email}"', '"/api/responsables"'):
        assert leaked not in source, f"Route de référentiel réapparue dans main.py : {leaked}"
