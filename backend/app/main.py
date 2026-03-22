"""
CLEF - FastAPI Backend
Main application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import logging

from app.mocks.service_factory import (
    get_sheets_service,
    use_mocks
)
from app.auth.routes import router as auth_router
from app.cache import get_cache
from app.services.valkey_service import ValkeyService

logger = logging.getLogger(__name__)
from app.routers import config_router, calendar_router, unites_locales_router
from app.routers import vehicles
from app.routers import reservations
from app.routers import reservations_valkey
from app.routers import carnet_bord
from app.routers import upload
from app.routers import alerts
from app.routers import sync
from app.routers import ical
from app.routers import import_vehicles
from app.routers import api_keys
from app.routers import benevoles
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

app = FastAPI(
    title="CLEF API",
    description="Gestion des Véhicules Croix-Rouge",
    version="0.1.0"
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
app.include_router(reservations_valkey.router)
app.include_router(carnet_bord.router)
app.include_router(upload.router)
app.include_router(alerts.router)
app.include_router(sync.router)
app.include_router(ical.router)
app.include_router(import_vehicles.router)
app.include_router(api_keys.router)
app.include_router(benevoles.router)
app.include_router(stats.router)
app.include_router(dossiers_reparation.router)
app.include_router(depenses.router)
app.include_router(fournisseurs.router)
app.include_router(valideurs.router)
app.include_router(contacts_cc.router)
app.include_router(approbation.router)
app.include_router(reminders.router)
app.include_router(super_admin_router)

# Cache instances
cache = get_cache()


@app.on_event("startup")
async def startup_event():
    """Initialize Redis connection and preload référentiels on startup"""
    try:
        # Connect to Redis
        await cache.connect()
        logger.info("Redis connection established")

        # Get ValkeyService for DT75 (default DT)
        # Note: In production, this should be configurable per DT
        if not cache.client:
            raise RuntimeError("Redis client not available")
        valkey = ValkeyService(redis_client=cache.client, dt="DT75")

        # Initialize DTs and ULs data if not present
        from scripts.init_ul_data import init_data_async
        await init_data_async(cache.client)
        logger.info("DT and UL initialization complete")

        # Preload référentiels from Google Sheets (optional - continue if not configured)
        try:
            sheets_service = get_sheets_service()

            # Preload bénévoles into Valkey with DT prefix
            benevoles = sheets_service.get_benevoles()
            from app.models.valkey_models import BenevoleData
            for benevole_dict in benevoles:
                # Map email to nivol if nivol not present (temporary compatibility)
                if "nivol" not in benevole_dict:
                    benevole_dict["nivol"] = benevole_dict.get("email", "unknown")
                # Ensure dt field is present
                if "dt" not in benevole_dict:
                    benevole_dict["dt"] = "DT75"
                benevole = BenevoleData(**benevole_dict)
                await valkey.set_benevole(benevole)
            logger.info(f"Preloaded {len(benevoles)} bénévoles into Valkey with DT prefix")

            # Preload responsables into Valkey with DT prefix
            responsables = sheets_service.get_responsables()
            from app.models.valkey_models import ResponsableData
            for responsable_dict in responsables:
                # Ensure dt field is present
                if "dt" not in responsable_dict:
                    responsable_dict["dt"] = "DT75"
                responsable = ResponsableData(**responsable_dict)
                await valkey.set_responsable(responsable)
            logger.info(f"Preloaded {len(responsables)} responsables into Valkey with DT prefix")
        except Exception as e:
            logger.warning(f"Could not preload référentiels from Google Sheets: {e}")
            logger.warning("Application will continue without preloaded référentiels")

        # Start scheduler for alerts
        start_scheduler()
        logger.info("Scheduler started for periodic alerts")

    except Exception as e:
        logger.error(f"Error during startup: {e}")
        logger.warning("Application will continue despite startup errors")


@app.on_event("shutdown")
async def shutdown_event():
    """Close Redis connection and stop scheduler on shutdown"""
    try:
        # Stop scheduler
        stop_scheduler()
        logger.info("Scheduler stopped")

        # Close Redis connection
        await cache.disconnect()
        logger.info("Redis connection closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

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


@app.get("/api/benevoles")
async def get_benevoles():
    """Get all volunteers from the referential"""
    sheets_service = get_sheets_service()
    benevoles = sheets_service.get_benevoles()
    return {
        "count": len(benevoles),
        "benevoles": benevoles,
        "using_mocks": use_mocks()
    }


@app.get("/api/benevoles/{email}")
async def get_benevole(email: str):
    """Get a specific volunteer by email"""
    sheets_service = get_sheets_service()
    benevole = sheets_service.get_benevole_by_email(email)
    if benevole is None:
        return {
            "error": "Volunteer not found",
            "email": email
        }
    return {
        "benevole": benevole,
        "using_mocks": use_mocks()
    }


@app.get("/api/responsables")
async def get_responsables():
    """Get all managers from the referential"""
    sheets_service = get_sheets_service()
    responsables = sheets_service.get_responsables()
    return {
        "count": len(responsables),
        "responsables": responsables,
        "using_mocks": use_mocks()
    }

