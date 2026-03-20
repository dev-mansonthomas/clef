"""UL configuration API endpoints."""
import logging
import re
import unicodedata
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.dependencies import require_authenticated_user
from app.auth.models import User
from app.services.valkey_dependencies import get_valkey_service
from app.services.valkey_service import ValkeyService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ul", tags=["ul-config"])

ROMAN_TO_INT = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
    "XI": 11,
    "XII": 12,
    "XIII": 13,
    "XIV": 14,
    "XV": 15,
    "XVI": 16,
    "XVII": 17,
    "XVIII": 18,
    "XIX": 19,
    "XX": 20,
}


class ULConfig(BaseModel):
    """Configuration d'une Unité Locale."""


def _normalize_label(value: str | None) -> str:
    if not value:
        return ""

    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char)).upper()


def _extract_paris_arrondissement(value: str | None) -> int | None:
    normalized = _normalize_label(value)

    digit_match = re.search(r"PARIS\s+([0-9]{1,2})\b", normalized)
    if digit_match:
        return int(digit_match.group(1))

    roman_match = re.search(
        r"PARIS\s+(XX|XIX|XVIII|XVII|XVI|XV|XIV|XIII|XII|XI|X|IX|VIII|VII|VI|V|IV|III|II|I)\b",
        normalized,
    )
    if roman_match:
        return ROMAN_TO_INT.get(roman_match.group(1))

    return None


def _ensure_ul_access(current_user: User, ul_id: str, ul_data: dict[str, Any]) -> None:
    if current_user.role != "Responsable UL":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="UL responsible access required",
        )

    if current_user.dt != ul_data.get("dt"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied for this Unité Locale",
        )

    user_ul = current_user.ul or current_user.perimetre
    normalized_user_ul = _normalize_label(user_ul)
    normalized_ul_name = _normalize_label(ul_data.get("nom"))

    if normalized_user_ul and normalized_user_ul == normalized_ul_name:
        return

    user_arrondissement = _extract_paris_arrondissement(user_ul)
    ul_arrondissement = _extract_paris_arrondissement(ul_data.get("nom"))
    if user_arrondissement and ul_arrondissement and user_arrondissement == ul_arrondissement:
        return

    logger.warning(
        "UL config access denied for %s on UL %s (%s)",
        current_user.email,
        ul_id,
        ul_data.get("nom"),
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied for this Unité Locale",
    )


@router.get("/{ul_id}/config")
async def get_ul_config(
    ul_id: str,
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service),
) -> dict[str, Any]:
    """Récupère la configuration d'une UL."""
    ul_data = await valkey.redis.json().get(f"{valkey.dt}:unite_locale:{ul_id}")
    if not ul_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unité Locale {ul_id} non trouvée",
        )

    _ensure_ul_access(current_user, ul_id, ul_data)

    return {
        "ul_id": ul_id,
        "nom": ul_data.get("nom"),
        "config": {},
        "message": "Aucune configuration disponible pour le moment",
    }


@router.put("/{ul_id}/config")
async def update_ul_config(
    ul_id: str,
    config: ULConfig,
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service),
) -> dict[str, Any]:
    """Met à jour la configuration d'une UL."""
    ul_data = await valkey.redis.json().get(f"{valkey.dt}:unite_locale:{ul_id}")
    if not ul_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unité Locale {ul_id} non trouvée",
        )

    _ensure_ul_access(current_user, ul_id, ul_data)

    return {
        "success": True,
        "message": "Configuration sauvegardée (aucun champ pour l'instant)",
        "config": config.model_dump(),
    }