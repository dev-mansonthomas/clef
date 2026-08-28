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


# `GET /api/alerts/status` a été SUPPRIMÉE le 2026-08-28. Elle n'avait aucun `Depends`,
# et le load balancer publie `/api/*` sur le domaine public : elle divulguait
# anonymement `service_account_email`, `use_mocks` et le nom de l'environnement.
#
# Elle a été supprimée plutôt que gardée, parce qu'elle ne servait à rien :
#
#   • aucun appelant — ni `admin`, ni `form`, ni e2e, ni les Apps Script ;
#   • `"enabled": True` était CODÉ EN DUR, alors que le job dépend de
#     `SCHEDULER_ENABLED` (scheduler.py) : la route répondait « activé » même
#     scheduler éteint, donc elle mentait précisément quand on l'interrogeait ;
#   • elle ne disait rien de ce qu'on voudrait savoir — dernière et prochaine
#     exécution, nombre d'alertes envoyées, erreurs ;
#   • ses deux seules valeurs exactes sont désormais servies sous guard par
#     `GET /admin/super/environnement`.
#
# ⚠️ Si le besoin de superviser ce job revient — il est légitime, c'est une tâche
# silencieuse — la route à écrire lit l'état RÉEL du scheduler
# (`job.next_run_time`), sous `require_dt_manager` comme `/trigger`. Ce n'est pas un
# correctif, c'est une petite fonctionnalité.

