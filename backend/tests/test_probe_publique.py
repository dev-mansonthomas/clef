"""`/api/test` était publique ET bavarde — deux propriétés à séparer.

La route était déclarée EN LIGNE dans `main.py`, fichier qui ne porte aucun `Depends` :
tout ce qui y est déclaré est public par construction, et c'est la famille du constat C1
(l'annuaire des bénévoles servi anonymement). Elle renvoyait `environment` et
`using_mocks`, désormais publiés sur le domaine public de la Croix-Rouge par le load
balancer, et de surcroît sondés à chaque déploiement.

Le besoin est double, et les deux moitiés n'ont pas le même public :

* une **sonde de routage** publique, qui prouve que `/api/*` atteint bien `clef-api` —
  elle doit rester sans authentification, sinon elle ne vérifie plus le routage ;
* un **diagnostic** (environnement, mode mock), qui appartient au super admin.

D'où `routers/probe.py` d'un côté, `GET /admin/super/environnement` de l'autre.
"""
import os
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["USE_MOCKS"] = "true"

from app.main import app  # noqa: E402

MAIN = Path(__file__).resolve().parent.parent / "app" / "main.py"

# Les seules routes qui ont le droit de rester en ligne dans main.py : elles ne
# divulguent rien et Cloud Run a besoin de la seconde comme sonde de démarrage.
ROUTES_EN_LIGNE_TOLEREES = {"/", "/health"}


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_la_sonde_repond_sans_authentification(client: TestClient):
    """C'est sa raison d'être : `01-gcp-deploy.sh` et la spec s'en servent.

    Une sonde qui exigerait une session ne vérifierait plus le routage `/api/*` du
    load balancer — elle vérifierait l'authentification.
    """
    reponse = client.get("/api/test")
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["status"] == "ok"


def test_la_sonde_ne_divulgue_rien_du_deploiement(client: TestClient):
    """Ni le nom de l'environnement, ni le fait que les services Google sont simulés.

    Le load balancer publie ce point d'entrée sur le domaine public : n'importe qui
    apprenait qu'une instance tournait en mock, et sous quel environnement.
    """
    corps = client.get("/api/test").json()
    interdits = {"environment", "using_mocks", "env", "mocks"}
    assert not (interdits & corps.keys()), (
        f"la sonde publique divulgue {sorted(interdits & corps.keys())} — "
        "ce diagnostic appartient à /admin/super/environnement"
    )


def test_le_diagnostic_exige_le_super_admin(client: TestClient):
    """Le besoin est réel — savoir qu'une production ne tourne pas en mock — mais gardé."""
    reponse = client.get("/admin/super/environnement")
    assert reponse.status_code in (401, 403), (
        f"le diagnostic répond {reponse.status_code} sans session : il doit être "
        "réservé au super admin"
    )


def test_le_statut_des_alertes_n_est_plus_servi(client: TestClient):
    """`GET /api/alerts/status` divulguait `service_account_email` sans authentification.

    Supprimée plutôt que gardée : aucun appelant, `"enabled": True` codé en dur alors
    que le job dépend de `SCHEDULER_ENABLED` — donc une réponse fausse précisément
    quand on l'interroge — et ses deux valeurs exactes sont désormais sous guard dans
    `GET /admin/super/environnement`. La surface la plus sûre est celle qui n'existe
    pas.
    """
    assert client.get("/api/alerts/status").status_code == 404


def test_toutes_les_routes_d_alertes_portent_un_guard():
    """Garde structurelle sur le router entier, pas sur la seule route supprimée.

    `POST /trigger` était gardée, `GET /status` non : l'oubli ne se voyait pas à la
    relecture, les deux étant à quinze lignes d'écart. Le test remonte l'arbre de
    dépendances de chaque route du router — ce qui couvre les deux formes, le
    `dependencies=[Depends(...)]` du décorateur comme le paramètre `Depends(...)`.
    """
    from fastapi.routing import APIRoute

    from app.auth import dependencies as guards

    attendus = {
        fonction
        for nom, fonction in vars(guards).items()
        if nom.startswith("require_") and callable(fonction)
    }
    assert attendus, "les guards ont été renommés — le test ne vérifie plus rien"

    def appels(dependant):
        for sous in dependant.dependencies:
            yield sous.call
            yield from appels(sous)

    # ⚠️ `app.routes` n'est PAS plat sur fastapi 0.141 : un router inclus y apparaît
    # comme un `_IncludedRouter`, et ses routes vivent dans `original_router`. Un
    # `isinstance(r, APIRoute)` sur `app.routes` ne voit donc que les routes déclarées
    # en ligne — soit exactement celles que ce fichier interdit. Sans cette descente,
    # le test passait sur une liste vide.
    def toutes(porteur):
        for r in getattr(porteur, "routes", []):
            if isinstance(r, APIRoute):
                yield r
            inclus = getattr(r, "original_router", None)
            if inclus is not None:
                yield from toutes(inclus)

    routes = [r for r in toutes(app) if r.path.startswith("/api/alerts")]
    assert routes, "le router des alertes a disparu — motif de chemin à revoir"
    for route in routes:
        assert attendus & set(appels(route.dependant)), (
            f"{sorted(route.methods)} {route.path} n'exige aucune authentification. "
            "Le load balancer publie /api/* sur le domaine public."
        )


def test_main_ne_declare_aucune_route_en_ligne_hors_tolerance():
    """Garde structurelle, comme pour le référentiel (C1).

    `main.py` n'a aucun `Depends` : une route ajoutée ici est publique, sans que rien
    ne le signale à la relecture. Le test échoue donc sur toute NOUVELLE route en
    ligne, ce qui force à passer par un router — où poser un guard est naturel.
    """
    source = MAIN.read_text(encoding="utf-8")
    routes = set(re.findall(r'^@app\.(?:get|post|put|patch|delete)\("([^"]+)"', source, re.M))
    inattendues = routes - ROUTES_EN_LIGNE_TOLEREES
    assert not inattendues, (
        f"routes déclarées en ligne dans main.py : {sorted(inattendues)}. "
        "Sans `Depends`, elles sont publiques par construction — passer par un router."
    )
    assert "/api/test" not in routes, (
        "/api/test doit vivre dans routers/probe.py"
    )
