"""Unités Locales API endpoints."""
import json
import logging
from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status

from app.models.unite_locale import (
    UniteLocale,
    UniteLocaleCreate,
    UniteLocaleUpdate,
    UniteLocaleListResponse
)
from app.auth.models import User
from app.auth.dependencies import require_authenticated_user, require_dt_manager
from app.cache import RedisCache, get_cache

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/{dt}/unites-locales",
    tags=["unites-locales"]
)


@router.get("", response_model=UniteLocaleListResponse)
async def list_unites_locales(
    dt: str,
    cache: Annotated[RedisCache, Depends(get_cache)],
    current_user: User = Depends(require_authenticated_user)
) -> UniteLocaleListResponse:
    """
    Liste des Unités Locales de la DT.
    
    Args:
        dt: Code de la Délégation Territoriale
        cache: Redis cache instance
        current_user: Authenticated user
        
    Returns:
        Liste des Unités Locales
    """
    try:
        # Get the set of UL IDs for this DT
        index_key = f"{dt}:unite_locales:index"
        ul_ids = await cache.client.smembers(index_key)

        if not ul_ids:
            return UniteLocaleListResponse(unites_locales=[], total=0)

        # Fetch each UL
        unites_locales = []
        for ul_id in ul_ids:
            ul_key = f"{dt}:unite_locale:{ul_id}"
            try:
                ul_data = await cache.client.json().get(ul_key)
                if ul_data:
                    unites_locales.append(UniteLocale(**ul_data))
                else:
                    logger.warning(f"UL {ul_id} in index but data not found at key {ul_key}")
            except Exception as e:
                logger.error(f"Error fetching UL {ul_id} from key {ul_key}: {e}", exc_info=True)
                # Continue to next UL instead of failing the entire request
                continue

        return UniteLocaleListResponse(
            unites_locales=unites_locales,
            total=len(unites_locales)
        )
    except Exception as e:
        logger.error(f"Error listing UL for {dt}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving Unités Locales"
        )


@router.get("/{ul_id}", response_model=UniteLocale)
async def get_unite_locale(
    dt: str,
    ul_id: str,
    cache: Annotated[RedisCache, Depends(get_cache)],
    current_user: User = Depends(require_authenticated_user)
) -> UniteLocale:
    """
    Détail d'une Unité Locale.
    
    Args:
        dt: Code de la Délégation Territoriale
        ul_id: ID de l'Unité Locale
        cache: Redis cache instance
        current_user: Authenticated user
        
    Returns:
        Unité Locale details
    """
    ul_key = f"{dt}:unite_locale:{ul_id}"
    ul_data = await cache.client.json().get(ul_key)

    if not ul_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unité Locale {ul_id} not found in {dt}"
        )

    return UniteLocale(**ul_data)


@router.post("", response_model=UniteLocale, status_code=status.HTTP_201_CREATED)
async def create_unite_locale(
    dt: str,
    ul: UniteLocaleCreate,
    cache: Annotated[RedisCache, Depends(get_cache)],
    current_user: User = Depends(require_dt_manager)
) -> UniteLocale:
    """
    Créer une Unité Locale (admin DT uniquement).
    
    Args:
        dt: Code de la Délégation Territoriale
        ul: Unité Locale data
        cache: Redis cache instance
        current_user: Authenticated DT manager
        
    Returns:
        Created Unité Locale
    """
    try:
        # Check if UL already exists
        ul_key = f"{dt}:unite_locale:{ul.id}"
        exists = await cache.exists(ul_key)

        if exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Unité Locale {ul.id} already exists in {dt}"
            )

        # Create UL with timestamp
        ul_data = UniteLocale(
            **ul.model_dump(),
            created_at=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        )

        # Store in Redis using JSON native storage
        await cache.client.json().set(ul_key, "$", ul_data.model_dump())

        # Add to index
        index_key = f"{dt}:unite_locales:index"
        await cache.client.sadd(index_key, ul.id)

        logger.info(f"Created UL {ul.id} in {dt} with key {ul_key}")
        return ul_data
    except HTTPException:
        # Re-raise HTTP exceptions (like 409 Conflict)
        raise
    except Exception as e:
        logger.error(f"Error creating UL {ul.id} in {dt}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating Unité Locale: {str(e)}"
        )


@router.put("/{ul_id}", response_model=UniteLocale)
async def update_unite_locale(
    dt: str,
    ul_id: str,
    ul: UniteLocaleUpdate,
    cache: Annotated[RedisCache, Depends(get_cache)],
    current_user: User = Depends(require_dt_manager)
) -> UniteLocale:
    """
    Modifier une Unité Locale (admin DT uniquement).

    Args:
        dt: Code de la Délégation Territoriale
        ul_id: ID de l'Unité Locale
        ul: Updated Unité Locale data
        cache: Redis cache instance
        current_user: Authenticated DT manager

    Returns:
        Updated Unité Locale
    """
    try:
        # Check if UL exists
        ul_key = f"{dt}:unite_locale:{ul_id}"
        ul_data = await cache.client.json().get(ul_key)

        if not ul_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unité Locale {ul_id} not found in {dt}"
            )

        # Update only provided fields
        current_ul = UniteLocale(**ul_data)
        update_data = ul.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(current_ul, field, value)

        # Store updated UL using JSON native storage
        await cache.client.json().set(ul_key, "$", current_ul.model_dump())

        logger.info(f"Updated UL {ul_id} in {dt}")
        return current_ul
    except HTTPException:
        # Re-raise HTTP exceptions (like 404 Not Found)
        raise
    except Exception as e:
        logger.error(f"Error updating UL {ul_id} in {dt}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating Unité Locale: {str(e)}"
        )


@router.delete("/{ul_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_unite_locale(
    dt: str,
    ul_id: str,
    cache: Annotated[RedisCache, Depends(get_cache)],
    current_user: User = Depends(require_dt_manager)
) -> None:
    """
    Supprimer une Unité Locale (admin DT uniquement).

    Args:
        dt: Code de la Délégation Territoriale
        ul_id: ID de l'Unité Locale
        cache: Redis cache instance
        current_user: Authenticated DT manager

    Returns:
        None (204 No Content on success)
    """
    try:
        # Check if UL exists
        ul_key = f"{dt}:unite_locale:{ul_id}"
        exists = await cache.exists(ul_key)

        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unité Locale {ul_id} not found in {dt}"
            )

        # Delete UL data
        await cache.client.delete(ul_key)

        # Remove from index
        index_key = f"{dt}:unite_locales:index"
        await cache.client.srem(index_key, ul_id)

        logger.info(f"Deleted UL {ul_id} from {dt}")
    except HTTPException:
        # Re-raise HTTP exceptions (like 404 Not Found)
        raise
    except Exception as e:
        logger.error(f"Error deleting UL {ul_id} in {dt}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting Unité Locale: {str(e)}"
        )

