"""Alert router for manual triggering and status."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any

from app.auth.dependencies import require_authenticated_user, require_dt_manager
from app.auth.models import User
from app.services.alert_service import AlertService
from app.services.config_service import ConfigService
from app.cache import get_cache

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/alerts",
    tags=["alerts"]
)


@router.post("/trigger", dependencies=[Depends(require_dt_manager)])
async def trigger_alerts(
    current_user: User = Depends(require_authenticated_user)
) -> Dict[str, Any]:
    """
    Manually trigger alert check and email sending.
    Only accessible by DT managers.
    
    Returns:
        Alert statistics
    """
    logger.info(f"Manual alert trigger by user: {current_user.email}")
    
    try:
        # Initialize services
        cache = get_cache()
        config_service = ConfigService(cache)
        alert_service = AlertService(config_service)
        
        # Run alert check
        result = await alert_service.check_and_send_alerts()
        
        return result
    except Exception as e:
        logger.error(f"Error triggering alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_alert_status() -> Dict[str, Any]:
    """
    Get alert service status.
    
    Returns:
        Status information
    """
    import os
    
    return {
        "enabled": True,
        "alert_delay_days": int(os.getenv("ALERT_DELAY_DAYS", "60")),
        "service_account_email": os.getenv("SERVICE_ACCOUNT_EMAIL", ""),
        "use_mocks": os.getenv("USE_MOCKS", "false").lower() == "true"
    }

