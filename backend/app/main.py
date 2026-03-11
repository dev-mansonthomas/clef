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
from app.cache import get_cache, CacheService

logger = logging.getLogger(__name__)
from app.routers import config_router, calendar_router
from app.routers import vehicles
from app.routers import reservations
from app.routers import carnet_bord
from app.routers import upload
from app.routers import alerts
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
app.include_router(vehicles.router)
app.include_router(reservations.router)
app.include_router(carnet_bord.router)
app.include_router(upload.router)
app.include_router(alerts.router)

# Cache instances
cache = get_cache()
cache_service = None


@app.on_event("startup")
async def startup_event():
    """Initialize Redis connection and preload référentiels on startup"""
    global cache_service

    try:
        # Connect to Redis
        await cache.connect()
        logger.info("Redis connection established")

        # Initialize cache service
        cache_service = CacheService(cache)

        # Preload référentiels from mocks
        sheets_service = get_sheets_service()

        # Preload bénévoles
        benevoles = sheets_service.get_benevoles()
        await cache_service.preload_benevoles(benevoles)
        logger.info(f"Preloaded {len(benevoles)} bénévoles into cache")

        # Preload responsables
        responsables = sheets_service.get_responsables()
        await cache_service.preload_responsables(responsables)
        logger.info(f"Preloaded {len(responsables)} responsables into cache")

        # Start scheduler for alerts
        start_scheduler()
        logger.info("Scheduler started for periodic alerts")

    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise


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

