"""Pytest configuration and fixtures."""
import csv
import os
from pathlib import Path

import pytest

# Set USE_MOCKS before any imports
os.environ["USE_MOCKS"] = "true"


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment variables."""
    # Already set above, but keep for clarity
    os.environ["USE_MOCKS"] = "true"
    yield


# ---------------------------------------------------------------------------
# Marqueur `integration` : exige un serveur Redis joignable
# ---------------------------------------------------------------------------
# Une partie des tests traverse le vrai chemin de données : ils passent par un
# endpoint qui résout `get_redis_service`, lequel utilise le singleton de cache
# et donc une connexion réelle. `fakeredis` ne les couvre pas, car ils
# n'injectent pas de client de test.
#
# Sans serveur, ces tests doivent être **ignorés**, pas mis en échec : un échec
# ferait passer une dépendance d'environnement absente pour une régression de
# code. La CI, elle, fournit un service `redis:8.10` — ils y sont donc exécutés.
# Voir docs/specs/ci-verte-redis-8.md, critère A4.

_REDIS_REACHABLE: bool | None = None


def _redis_reachable() -> bool:
    """Sonde une seule fois le serveur configuré par `REDIS_URL`."""
    global _REDIS_REACHABLE
    if _REDIS_REACHABLE is None:
        import redis

        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            client = redis.Redis.from_url(url, socket_connect_timeout=1)
            client.ping()
            client.close()
            _REDIS_REACHABLE = True
        except Exception:
            _REDIS_REACHABLE = False
    return _REDIS_REACHABLE


def pytest_runtest_setup(item):
    """Ignore les tests `integration` quand aucun serveur Redis n'est joignable."""
    if item.get_closest_marker("integration") and not _redis_reachable():
        pytest.skip(
            "Aucun serveur Redis joignable sur "
            f"{os.getenv('REDIS_URL', 'redis://localhost:6379/0')} — "
            "démarrer `docker compose up -d redis`"
        )


# ---------------------------------------------------------------------------
# Repli sur fakeredis quand aucun serveur n'est joignable
# ---------------------------------------------------------------------------
# Depuis la tâche N2, l'authentification lit le référentiel des bénévoles dans Redis.
# Tout test qui s'authentifie en dépend donc — soit l'essentiel de la suite. Sans
# serveur, on obtiendrait 87 échecs là où il n'y a aucun défaut de code.
#
# Plutôt que de marquer ces tests `integration` et d'en ignorer la majorité, on
# substitue un fakeredis au client du cache, en remplaçant `cache.connect()`. Le code
# de production n'est pas touché : sa logique de reconnexion (dependencies.py) appelle
# `connect()` et obtient un client neuf, lié à la boucle d'événements courante — ce
# qui règle du même coup les « Event loop is closed » entre TestClient successifs.

async def _seed_referentiel(client) -> None:
    """Peuple le référentiel comme le fait le démarrage de l'app.

    Reproduit le préchargement de `app/main.py` : sans bénévoles en base, la
    résolution des rôles échoue et tous les tests authentifiés reçoivent un 401.
    """
    from app.mocks.service_factory import get_sheets_service
    from app.models.redis_models import BenevoleData
    from app.services.redis_service import RedisService

    store = RedisService(redis_client=client, dt="DT75")
    for raw in get_sheets_service().get_benevoles():
        raw = dict(raw)
        raw.setdefault("nivol", raw.get("email", "unknown"))
        raw.setdefault("dt", "DT75")
        # Le mock Sheets porte encore l'ancien champ `role`. Le traduire vers le
        # modèle actuel — `responsable_ul` + `fonctions_dt` — sinon tous les
        # utilisateurs de test deviennent de simples bénévoles et les tests de rôle
        # échouent pour une raison sans rapport avec ce qu'ils vérifient.
        legacy_role = raw.pop("role", None)
        raw["responsable_ul"] = legacy_role == "responsable_ul"
        raw["fonctions_dt"] = ["Gestionnaire DT"] if legacy_role == "responsable_dt" else []
        raw.pop("statut", None)  # « Actif » côté feuille ; CLEF possède ce champ
        try:
            await store.set_benevole(BenevoleData(**raw))
        except Exception:
            # Une ligne de référentiel malformée ne doit pas faire tomber la suite.
            continue


#: Le référentiel d'un Redis réel n'est peuplé qu'une fois par session : les écritures
#: persistent, contrairement au fakeredis recréé à chaque connexion.
_REAL_SEEDED = False


@pytest.fixture(autouse=True)
def redis_backend(monkeypatch):
    """Garantit un datastore utilisable **et peuplé**, réel ou simulé.

    Les deux moitiés comptent. Depuis la tâche N2, l'authentification résout les rôles
    depuis le référentiel Redis : un datastore joignable mais **vide** fait échouer tout
    test qui s'authentifie autrement qu'en `EMAIL_GESTIONNAIRE_DT`.

    C'est précisément la configuration de la CI — service `redis:8.10` frais — et c'est
    ce qui l'a fait échouer alors que la suite passait en local, où le référentiel avait
    été peuplé par l'amorçage de la stack de développement. Le peuplement ne peut donc
    pas dépendre de l'environnement.
    """
    global _REAL_SEEDED

    if _redis_reachable():
        # Datastore réel : peupler une seule fois, les écritures persistant.
        if not _REAL_SEEDED:
            import asyncio

            from app.cache import get_cache

            async def _prepare():
                cache = get_cache()
                if not cache._connected or cache.client is None:
                    await cache.connect()
                await _seed_referentiel(cache.client)
                # Laisser le cache dans l'état où les tests l'attendent : la connexion
                # ouverte ici est liée à *cette* boucle, qui va disparaître.
                cache.client = None
                cache._connected = False

            asyncio.run(_prepare())
            _REAL_SEEDED = True
        yield
        return

    import fakeredis.aioredis

    from app.cache import get_cache

    cache = get_cache()

    async def _connect_fake():
        cache.client = fakeredis.aioredis.FakeRedis(decode_responses=True)
        cache._connected = True
        await _seed_referentiel(cache.client)

    monkeypatch.setattr(cache, "connect", _connect_fake)
    cache.client = None
    cache._connected = False
    yield


@pytest.fixture(autouse=True)
def reset_cache_after_test():
    """Reset the global cache singleton after each test to prevent event loop leaks.

    TestClient creates its own event loop. If the app startup connects to Redis,
    that connection is bound to the TestClient's loop. When the loop closes, the
    connection becomes stale but the cache singleton still holds it, causing
    'Future attached to a different loop' errors in subsequent tests.
    """
    yield
    from app.cache import get_cache
    cache = get_cache()
    if cache._connected:
        cache.client = None
        cache._connected = False


# ---------------------------------------------------------------------------
# Fixtures CSV pour l'import du référentiel véhicules
# ---------------------------------------------------------------------------
# Ces CSV étaient auparavant des fichiers sous tests/fixtures/. Ils n'ont jamais
# été committés : la règle `.gitignore` `*.csv`, posée pour protéger les données
# personnelles des bénévoles, les a avalés, et la machine qui les détenait a été
# supprimée (docs/TODO.md H2). Ils sont désormais **générés**, ce qui supprime
# cette classe de panne et rend la forme attendue explicite et vérifiable.
#
# La forme est celle documentée dans docs/specs/import-vehicules-csv.md.

#: Les 19 en-têtes du référentiel « Véhicules DT75 & UL ».
#: ⚠️ Les fautes d'orthographe (« Syntéthique », « récuperer ») sont celles du
#: fichier source et doivent être conservées : la détection d'en-tête
#: (`HEADER_MAPPINGS` dans app/routers/import_vehicles.py) s'appuie sur les
#: libellés réels, et ces deux colonnes ne sont volontairement pas reconnues.
VEHICLES_CSV_HEADERS = [
    "DT 75 / UL",
    "Immat",
    "Indicatif",
    "Opérationnel Mécanique",
    "Raison Indispo",
    "Prochain Controle Technique",
    "Prochain Controle Pollution",
    "Marque",
    "Modèle",
    "Type",
    "Date de MEC",
    "Nom Syntéthique",
    "Carte Grise",
    "# de Place",
    "Commentaires",
    "Lieu de Stationnement",
    "Instructions pour récuperer le véhicule (lien vers google docs)",
    "Assurance",
    "N° Serie BAUS",
]

#: 4 lignes de métadonnées, ignorées par `skip_lines=4` (valeur détectée par
#: l'endpoint de prévisualisation). Contenu volontairement inutilisable comme
#: données : ce sont les lignes de titre du Google Sheet source.
_METADATA_LINES = [
    ["Référentiel Véhicules — export de test"],
    ["Délégation Territoriale de Paris (DT75)"],
    ["Document fictif — aucune donnée réelle"],
    [],
]


def _vehicle_row(
    dt_ul: str,
    immat: str,
    indicatif: str,
    marque: str,
    modele: str,
    type_vehicule: str,
    nom_synthetique: str,
) -> list[str]:
    """Construit une ligne de 19 colonnes conforme à l'en-tête du référentiel."""
    return [
        dt_ul,
        immat,
        indicatif,
        "Dispo",
        "",
        "2027-06-30",
        "2027-06-30",
        marque,
        modele,
        type_vehicule,
        "12/03/2020",
        nom_synthetique,
        f"CG-{immat.replace('-', '')}",
        "3",
        "",
        "Garage fictif",
        "",
        "Contrat fictif 2026",
        f"BAUS-{immat.replace('-', '')}",
    ]


def _write_csv(path: Path, rows: list[list[str]]) -> Path:
    """Écrit les lignes en CSV UTF-8 sans ligne vide finale parasite."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(rows)
    return path


@pytest.fixture
def vehicles_import_sample_csv(tmp_path: Path) -> Path:
    """CSV nominal d'import, à la forme exigée par les tests d'import.

    | Contrainte | Valeur |
    |---|---|
    | Lignes totales | 12 |
    | Lignes de métadonnées | 4 (`skip_lines=4`) |
    | Ligne d'en-têtes | 5 |
    | Colonnes | 19 |
    | Lignes de données | 5 (lignes 6 à 10) |
    | Dont immatriculation `N/A` | 1, ligne 9 |
    | Lignes vides finales | 2 (lignes 11 et 12) |

    Les deux lignes vides finales sont significatives : elles reproduisent la
    queue du Google Sheet exporté et produisent 2 des 3 entrées `errors` que
    `test_import_csv_all_fields_saved_to_redis` borne à 3.
    """
    rows: list[list[str]] = [*_METADATA_LINES, list(VEHICLES_CSV_HEADERS)]

    # Lignes 6 à 10 : 5 lignes de données, dont celle de la ligne 9 invalide.
    rows.append(_vehicle_row("UL Paris 1", "AA-101-AA", "PARIS-01-01",
                             "Renault", "Master", "VSAV", "vsav-paris-01"))
    rows.append(_vehicle_row("UL Paris 5", "AB-202-BB", "PARIS-05-01",
                             "Peugeot", "Boxer", "VPSP", "vpsp-paris-05"))
    rows.append(_vehicle_row("UL Paris 12", "AC-303-CC", "PARIS-12-01",
                             "Citroën", "Jumper", "VL", "vl-paris-12"))
    # Ligne 9 : immatriculation N/A → ignorée, pas mise en erreur bloquante.
    rows.append(_vehicle_row("UL Paris 15", "N/A", "PARIS-15-01",
                             "Renault", "Trafic", "VL", "vl-paris-15"))
    rows.append(_vehicle_row("UL Paris 20", "AD-404-DD", "PARIS-20-01",
                             "Ford", "Transit", "VPSP", "vpsp-paris-20"))

    # Lignes 11 et 12 : queue d'export vide.
    rows.append([])
    rows.append([])

    assert len(rows) == 12, "La forme attendue est de 12 lignes exactement"
    return _write_csv(tmp_path / "vehicles_import_sample.csv", rows)


@pytest.fixture
def vehicles_no_indicatif_csv(tmp_path: Path) -> Path:
    """CSV d'import sans indicatif exploitable (régression du ticket 16.4).

    Deux lignes de données : l'une sans indicatif du tout, l'autre avec le tiret
    que le Google Sheet utilise pour « pas d'indicatif ». Les deux doivent être
    importées, l'indicatif n'étant pas un champ requis.
    """
    rows: list[list[str]] = [*_METADATA_LINES, list(VEHICLES_CSV_HEADERS)]
    rows.append(_vehicle_row("UL Paris 18", "GR-319-XF", "",
                             "Renault", "Kangoo", "VL", "vl-paris-18"))
    rows.append(_vehicle_row("UL Paris 19", "GR-320-AB", "-",
                             "Dacia", "Dokker", "VL", "vl-paris-19"))

    assert len(rows) == 7, "4 métadonnées + en-tête + 2 lignes de données"
    return _write_csv(tmp_path / "vehicles_no_indicatif.csv", rows)

