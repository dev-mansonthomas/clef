"""
CLEF - FastAPI Backend
Main application entry point
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import logging

from app.mocks.service_factory import (
    assert_mocks_not_in_production,
    get_sheets_service,
    use_mocks
)
from app.auth.routes import router as auth_router
from app.cache import get_cache
from app.services.redis_service import RedisService

# ⚠️ Sans configuration, le logger racine de Python reste à WARNING : TOUS les
# `logger.info` du backend étaient donc perdus, y compris la ligne de compte rendu de la
# synchronisation du référentiel — « N créés, N erreurs de ligne ». Constaté le
# 2026-08-29 : les journaux Cloud Run montraient l'avertissement de réconciliation, mais
# pas la cause qui le précédait. Les journaux d'accès d'uvicorn passaient, eux, parce
# qu'uvicorn configure ses propres loggers — ce qui rendait l'absence invisible.
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger(__name__)
from app.routers import config_router, calendar_router, unites_locales_router
from app.routers import vehicles
from app.routers import reservations
from app.routers import reservations_store
from app.routers import carnet_bord
from app.routers import upload
from app.routers import alerts
from app.routers import probe
from app.routers import sync
from app.routers import ical
from app.routers import import_vehicles
from app.routers import api_keys
from app.routers import benevoles
from app.routers.benevoles import directory_router as benevoles_directory_router
from app.routers import stats
from app.routers import fournisseurs
from app.routers import valideurs
from app.routers import contacts_cc
from app.routers import dossiers_reparation
from app.routers import approbation
from app.routers import depenses
from app.routers import reminders
from app.admin.super_admin_routes import router as super_admin_router
from app.scheduler import start_scheduler, stop_scheduler

# Garde-fou S1 : refuse l'import — donc l'existence de l'app — si les mocks sont
# actifs en production. Volontairement **au niveau module** et non dans le `lifespan` :
# celui-ci enveloppe son démarrage dans un `except Exception` qui journalise puis
# continue, ce qui avalerait l'erreur et laisserait l'application servir.
assert_mocks_not_in_production()

# Cache instances
cache = get_cache()


async def _bootstrap_referentiel_mock(redis_store: RedisService) -> None:
    """Peuple le référentiel depuis le mock Sheets — **développement uniquement**.

    Sans utilisateurs en base, personne ne peut se connecter en local : depuis la tâche
    N2 l'authentification lit le référentiel Redis. Cet amorçage remplace le
    préchargement de production retiré, et n'est appelé que si `use_mocks()`.

    Le mock porte encore l'ancien champ `role`, que `BenevoleData` ignore désormais :
    il est traduit ici vers `responsable_ul` / `fonctions_dt`. Sans cette traduction,
    tous les comptes de développement seraient de simples bénévoles et l'écran
    d'administration DT deviendrait inaccessible en local, sans cause visible.
    """
    from app.models.redis_models import BenevoleData

    try:
        raw_benevoles = get_sheets_service().get_benevoles()
    except Exception as e:
        logger.warning("Amorçage du référentiel impossible : %s", e)
        return

    seeded = 0
    for raw in raw_benevoles:
        raw = dict(raw)
        raw.setdefault("nivol", raw.get("email", "unknown"))
        raw.setdefault("dt", redis_store.dt)
        legacy_role = raw.pop("role", None)
        raw["responsable_ul"] = legacy_role == "responsable_ul"
        raw["fonctions_dt"] = (
            ["Gestionnaire DT"] if legacy_role == "responsable_dt" else []
        )
        raw.pop("statut", None)  # « Actif » côté feuille ; CLEF possède ce champ
        try:
            await redis_store.set_benevole(BenevoleData(**raw))
            seeded += 1
        except Exception as e:
            logger.warning("Bénévole d'amorçage ignoré (%s) : %s", raw.get("nivol"), e)

    logger.warning(
        "USE_MOCKS=true — référentiel amorcé avec %d bénévole(s) fictifs. "
        "Ce n'est pas un chemin de production : la synchronisation Apps Script est "
        "la seule source réelle.",
        seeded,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cycle de vie de l'application : connexion Redis, préchargement, scheduler.

    Remplace les anciens `@app.on_event("startup"/"shutdown")`. Starlette 1.0 a
    supprimé `on_event()` et `add_event_handler()` (encode/starlette#3117) ;
    FastAPI n'en conserve qu'un shim déprécié. `lifespan` est la seule API portée.
    """
    # --- Démarrage ---
    # Annoncer le mode avant toute autre chose : le défaut local de docker-compose est
    # le mode mock, et démarrer dans le mauvais mode sans le voir est une confusion
    # coûteuse. En mock, l'app sert des données fictives, accepte des jetons signés
    # avec un secret public du dépôt et réduit le chiffrement KMS à du base64 (S1, S2)
    # — d'où le niveau WARNING, pour que ça ressorte d'un flot d'INFO.
    if use_mocks():
        logger.warning(
            "USE_MOCKS=true — services Google et OIDC simulés, données fictives, "
            "aucune credential requise. Ne jamais utiliser en production."
        )
    else:
        logger.info(
            "USE_MOCKS=false — services Google réels "
            "(GOOGLE_APPLICATION_CREDENTIALS requis)."
        )

    try:
        # Connect to Redis
        await cache.connect()
        logger.info("Redis connection established")

        # Get RedisService for DT75 (default DT)
        # Note: In production, this should be configurable per DT
        if not cache.client:
            raise RuntimeError("Redis client not available")
        redis_store = RedisService(redis_client=cache.client, dt="DT75")

        # Initialize DTs and ULs data if not present
        from scripts.init_ul_data import init_data_async
        await init_data_async(cache.client)
        logger.info("DT and UL initialization complete")

        # Le préchargement du référentiel depuis Google Sheets a été **retiré** : il
        # constituait un second chemin d'écriture, avec un contrat différent de celui
        # de la synchronisation (repli `email → nivol` qui stockait un bénévole sous
        # son email en guise de clé primaire). Deux chemins, deux contrats, la même
        # donnée. Conformément à l'ADR 0002, la synchronisation Apps Script
        # (`POST /api/sync/{dt}/benevoles`) est le **seul** pont depuis Sheets.
        #
        # Reste une commodité de développement, explicitement gardée.
        if use_mocks():
            await _bootstrap_referentiel_mock(redis_store)

        # Start scheduler for alerts
        start_scheduler()
        logger.info("Scheduler started for periodic alerts")

    except Exception as e:
        logger.error(f"Error during startup: {e}")
        logger.warning("Application will continue despite startup errors")

    yield

    # --- Arrêt ---
    try:
        # Stop scheduler
        stop_scheduler()
        logger.info("Scheduler stopped")

        # Close Redis connection
        await cache.disconnect()
        logger.info("Redis connection closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Documentation interactive : FERMÉE par défaut.
#
# FastAPI expose /docs, /redoc et /openapi.json sans authentification. Le service
# Cloud Run est déployé avec `allUsers` / `roles/run.invoker` — il le faut, c'est une
# application web publique dont les gardes sont applicatifs. Le schéma OpenAPI
# décrit alors, à qui le demande, les 86 routes : les routes super-admin, la gestion
# des clés d'API, le nom de l'en-tête X-API-Key de la synchronisation, le fait que
# /api/approbation/{token} n'est pas authentifiée, et les modèles du référentiel
# bénévoles (nivol, email, telephone, ul).
#
# Ça ne donne aucun accès — les gardes tiennent — mais ça supprime tout tâtonnement
# pour qui sonde ensuite ces surfaces. Le défaut est donc `false`, et
# docker-compose.yml pose `true` pour le développement local.
_api_docs_enabled = os.getenv("ENABLE_API_DOCS", "false").lower() == "true"

app = FastAPI(
    title="CLEF API",
    description="Gestion des Véhicules Croix-Rouge",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if _api_docs_enabled else None,
    redoc_url="/redoc" if _api_docs_enabled else None,
    openapi_url="/openapi.json" if _api_docs_enabled else None,
)

# CORS configuration for local development
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:4200,http://localhost:4202,http://localhost:8000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(config_router)
app.include_router(calendar_router)
app.include_router(unites_locales_router)
app.include_router(vehicles.router)
app.include_router(reservations.router)
app.include_router(reservations_store.router)
app.include_router(carnet_bord.router)
app.include_router(upload.router)
app.include_router(alerts.router)
app.include_router(sync.router)
app.include_router(ical.router)
app.include_router(import_vehicles.router)
app.include_router(api_keys.router)
app.include_router(benevoles.router)
app.include_router(benevoles_directory_router)
app.include_router(stats.router)
app.include_router(dossiers_reparation.router)
app.include_router(depenses.router)
app.include_router(fournisseurs.router)
app.include_router(valideurs.router)
app.include_router(contacts_cc.router)
app.include_router(approbation.router)
app.include_router(reminders.router)
app.include_router(super_admin_router)
app.include_router(probe.router)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "CLEF API",
        "version": "0.1.0",
        "status": "running"
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    redis_status = "disconnected"
    try:
        if cache._connected and cache.client:
            await cache.client.ping()
            redis_status = "connected"
    except Exception:
        pass

    return {
        "status": "healthy",
        "redis": redis_status
    }

# Les routes /api/benevoles, /api/benevoles/{email} et /api/responsables vivaient ici,
# déclarées en ligne — donc sans aucun guard, ce fichier n'ayant pas de `Depends`.
# L'annuaire des bénévoles était public : nom, prénom, email et UL servis à quiconque
# (constat C1, RGPD). Elles lisaient en outre Google Sheets en direct.
#
# `/api/benevoles` est désormais servie par `routers/benevoles.directory_router` :
# authentifiée, cadrée sur la délégation de la session, et lue dans Redis.
# Les deux autres n'avaient aucun appelant et ont été supprimées.
#
# ⚠️ Ne pas déclarer de route ici : sans `Depends`, elle serait publique par
# construction. Passer par un router avec un guard.
#
# `GET /api/test` est partie pour cette raison. Elle divulguait `environment` et
# `using_mocks` sans authentification, ce que le load balancer publie maintenant sur le
# domaine public. Elle vit en `routers/probe.py` — toujours publique, parce que c'est
# une sonde de routage, mais sans rien dire du déploiement ; le diagnostic est passé
# derrière le guard super-admin (`GET /admin/super/environnement`).
