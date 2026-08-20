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

logger = logging.getLogger(__name__)
from app.routers import config_router, calendar_router, unites_locales_router
from app.routers import vehicles
from app.routers import reservations
from app.routers import reservations_store
from app.routers import carnet_bord
from app.routers import upload
from app.routers import alerts
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

        # Preload référentiels from Google Sheets (optional - continue if not configured)
        try:
            sheets_service = get_sheets_service()

            # Preload bénévoles into Redis with DT prefix
            benevoles = sheets_service.get_benevoles()
            from app.models.redis_models import BenevoleData
            for benevole_dict in benevoles:
                # Map email to nivol if nivol not present (temporary compatibility)
                if "nivol" not in benevole_dict:
                    benevole_dict["nivol"] = benevole_dict.get("email", "unknown")
                # Ensure dt field is present
                if "dt" not in benevole_dict:
                    benevole_dict["dt"] = "DT75"
                benevole = BenevoleData(**benevole_dict)
                await redis_store.set_benevole(benevole)
            logger.info(f"Preloaded {len(benevoles)} bénévoles into Redis with DT prefix")

            # Preload responsables into Redis with DT prefix
            responsables = sheets_service.get_responsables()
            from app.models.redis_models import ResponsableData
            for responsable_dict in responsables:
                # Ensure dt field is present
                if "dt" not in responsable_dict:
                    responsable_dict["dt"] = "DT75"
                responsable = ResponsableData(**responsable_dict)
                await redis_store.set_responsable(responsable)
            logger.info(f"Preloaded {len(responsables)} responsables into Redis with DT prefix")
        except Exception as e:
            logger.warning(f"Could not preload référentiels from Google Sheets: {e}")
            logger.warning("Application will continue without preloaded référentiels")

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


app = FastAPI(
    title="CLEF API",
    description="Gestion des Véhicules Croix-Rouge",
    version="0.1.0",
    lifespan=lifespan,
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

@app.get("/api/test")
async def test_endpoint():
    """Test endpoint for development"""
    return {
        "message": "Test endpoint working",
        "environment": os.getenv("ENV", "unknown"),
        "using_mocks": use_mocks()
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
