"""
CLEF - FastAPI Backend
Main application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis
import os

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
        "environment": os.getenv("ENV", "unknown")
    }

