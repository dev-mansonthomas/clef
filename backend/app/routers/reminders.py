"""Reminders API endpoints."""
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, status

from app.auth.models import User
from app.auth.dependencies import require_authenticated_user
from app.services.valkey_dependencies import get_valkey_service
from app.services.valkey_service import ValkeyService
from app.services.reminder_service import ReminderService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/{dt}/reminders",
    tags=["reminders"],
)


@router.post("/check-devis", status_code=status.HTTP_200_OK)
async def check_overdue_devis(
    dt: str,
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service),
) -> Dict[str, Any]:
    """Check for devis awaiting approval past the configured reminder delay."""
    reminder_svc = ReminderService(valkey)
    overdue = await reminder_svc.check_overdue_devis()
    delai = await reminder_svc.get_delai_rappel()
    return {
        "delai_jours": delai,
        "overdue_count": len(overdue),
        "overdue_devis": overdue,
    }

