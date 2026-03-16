"""Statistics API endpoints."""
import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends

from app.auth.models import User
from app.auth.dependencies import require_authenticated_user
from app.services.valkey_dependencies import get_valkey_service
from app.services.valkey_service import ValkeyService
from app.services.stats_service import StatsService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/{dt}",
    tags=["stats"]
)


@router.get("/stats")
async def get_stats(
    dt: str,
    current_user: User = Depends(require_authenticated_user),
    valkey_service: ValkeyService = Depends(get_valkey_service)
) -> Dict[str, Any]:
    """
    Get dashboard statistics for vehicles.
    
    Returns statistics including:
    - Total vehicles count
    - Available/unavailable vehicles
    - CT status (en_retard, dans_2_mois, ok)
    - Pollution status (en_retard, dans_2_mois, ok)
    - List of vehicles requiring attention (alertes)
    
    Args:
        dt: DT identifier
        current_user: Authenticated user
        valkey_service: Valkey service instance
        
    Returns:
        Statistics dictionary
    """
    stats = await StatsService.get_dashboard_stats(valkey_service)
    return stats

