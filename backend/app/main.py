"""
CLEF - FastAPI Backend
Main application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis
import os

from app.mocks.service_factory import (
    get_sheets_service,
    use_mocks
)

app = FastAPI(
    title="CLEF API",
    description="Gestion des Véhicules Croix-Rouge",
    version="0.1.0"
)

# CORS configuration for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis connection
redis_client = None

@app.on_event("startup")
async def startup_event():
    """Initialize Redis connection on startup"""
    global redis_client
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    redis_client = redis.Redis(
        host=redis_host,
        port=redis_port,
        decode_responses=True
    )

@app.on_event("shutdown")
async def shutdown_event():
    """Close Redis connection on shutdown"""
    if redis_client:
        redis_client.close()

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
        if redis_client and redis_client.ping():
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


@app.get("/api/vehicles")
async def get_vehicles():
    """Get all vehicles from the referential"""
    sheets_service = get_sheets_service()
    vehicles = sheets_service.get_vehicules()
    return {
        "count": len(vehicles),
        "vehicles": vehicles,
        "using_mocks": use_mocks()
    }


@app.get("/api/vehicles/{nom_synthetique}")
async def get_vehicle(nom_synthetique: str):
    """Get a specific vehicle by synthetic name"""
    sheets_service = get_sheets_service()
    vehicle = sheets_service.get_vehicule_by_nom_synthetique(nom_synthetique)
    if vehicle is None:
        return {
            "error": "Vehicle not found",
            "nom_synthetique": nom_synthetique
        }
    return {
        "vehicle": vehicle,
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

