"""
FastAPI dependencies for authentication and authorization.
"""
import logging
from typing import Optional

from fastapi import Depends, HTTPException, status, Cookie

from .models import User, TokenData
from .service import AuthService
from .config import auth_settings
from .google_oauth import GoogleOAuthService
from .mock_instance import okta_mock

logger = logging.getLogger(__name__)

# Global instances
auth_service = AuthService()
google_oauth = GoogleOAuthService()


async def _referentiel_store():
    """Construit le `RedisService` de la délégation pour la résolution des rôles.

    Importé tardivement pour éviter un cycle : `app.services.redis_service` importe
    des modèles qui, en bout de chaîne, atteignent le paquet d'authentification.
    """
    from app.cache import get_cache
    from app.services.redis_service import RedisService

    cache = get_cache()

    # Le cache est un singleton de processus, et sa connexion est liée à la boucle
    # d'événements qui l'a ouverte. Si cette boucle a disparu — bascule Redis,
    # maintenance Memorystore, ou plusieurs TestClient dans un même test — le client
    # survit mais toute commande lève « Event loop is closed ». L'authentification
    # dépendant maintenant du datastore, un client mort la bloquerait définitivement.
    # On sonde donc, et on rouvre au besoin.
    #
    # Coût : un aller-retour PING par requête authentifiée. À comparer à ce que ce
    # chemin faisait avant N2 — un appel HTTP complet à l'API Google Sheets.
    try:
        if not cache._connected or cache.client is None:
            await cache.connect()
        else:
            await cache.client.ping()
    except Exception as exc:
        logger.info("Connexion Redis inutilisable (%s), réouverture", exc)
        cache.client = None
        cache._connected = False
        await cache.connect()

    return RedisService(redis_client=cache.client, dt=auth_settings.default_dt)


async def get_current_user(
    session_token: Optional[str] = Cookie(None, alias=auth_settings.session_cookie_name)
) -> Optional[User]:
    """
    Get current authenticated user from session cookie.

    Args:
        session_token: Session cookie containing JWT token

    Returns:
        User object if authenticated, None otherwise
    """
    if not session_token:
        return None

    try:
        # Verify token
        if auth_settings.use_mocks and okta_mock:
            # Mock mode: use mock verification
            token_claims = okta_mock.verify_token(session_token)
        else:
            # Production: Verify Google ID token
            token_claims = google_oauth.verify_id_token(session_token)

            # Validate email domain
            email = token_claims.get("email")
            if not email or not google_oauth.validate_email_domain(email):
                return None

        # Extract token data
        token_data = TokenData(
            email=token_claims["email"],
            name=token_claims.get("name"),
            given_name=token_claims.get("given_name"),
            family_name=token_claims.get("family_name"),
            sub=token_claims["sub"]
        )

        # Get user with role information. Le référentiel vit dans Redis (N2).
        redis_store = await _referentiel_store()
        user = await auth_service.get_user_from_token(token_data, redis_store)
        return user

    except Exception as exc:
        # Journaliser avant d'abandonner. Ce `except` muet est le constat M2 : c'est
        # lui qui a masqué pendant des mois le bug de fuseau horaire, puis M31. Une
        # authentification qui échoue en silence est indiagnosticable.
        logger.warning(
            "Authentification refusée : %s: %s", type(exc).__name__, exc
        )
        return None


async def require_authenticated_user(
    current_user: Optional[User] = Depends(get_current_user)
) -> User:
    """
    Require an authenticated user.
    
    Args:
        current_user: Current user from get_current_user dependency
        
    Returns:
        User object
        
    Raises:
        HTTPException: 401 if not authenticated
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return current_user


async def require_dt_manager(
    current_user: User = Depends(require_authenticated_user)
) -> User:
    """
    Require DT manager role.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User object
        
    Raises:
        HTTPException: 403 if not DT manager
    """
    if not auth_service.is_dt_manager(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="DT manager access required"
        )
    return current_user


async def require_ul_responsible(
    current_user: User = Depends(require_authenticated_user)
) -> User:
    """
    Require UL responsible role (includes DT manager).
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User object
        
    Raises:
        HTTPException: 403 if not UL responsible or DT manager
    """
    if not auth_service.is_ul_responsible(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="UL responsible access required"
        )
    return current_user


def user_is_super_admin(user: User) -> bool:
    """Check if user is the configured super admin."""
    if not auth_settings.super_admin_email:
        return False
    return user.email == auth_settings.super_admin_email


async def require_super_admin(
    current_user: User = Depends(require_authenticated_user)
) -> User:
    """
    Require super admin role.

    Raises:
        HTTPException: 403 if not super admin
    """
    if not user_is_super_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )
    return current_user


# Convenience aliases
is_authenticated = require_authenticated_user
is_dt_manager = require_dt_manager
is_ul_responsible = require_ul_responsible

