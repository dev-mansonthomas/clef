"""
FastAPI dependencies for authentication and authorization.
"""
from typing import Optional
from fastapi import Depends, HTTPException, status, Cookie
from .models import User, TokenData
from .service import AuthService
from .config import auth_settings
from .google_oauth import GoogleOAuthService
from .mock_instance import okta_mock


# Global instances
auth_service = AuthService()
google_oauth = GoogleOAuthService()


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

        # Get user with role information
        user = auth_service.get_user_from_token(token_data)
        return user

    except Exception:
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


# Convenience aliases
is_authenticated = require_authenticated_user
is_dt_manager = require_dt_manager
is_ul_responsible = require_ul_responsible

