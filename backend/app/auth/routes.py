"""
Authentication routes for Google OAuth SSO.
"""
import secrets
import json
import base64
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Response, Query, Depends
from fastapi.responses import RedirectResponse
from .models import User, LoginResponse
from .config import auth_settings
from .dependencies import get_current_user, require_dt_manager
from .google_oauth import GoogleOAuthService
from .mock_instance import okta_mock


router = APIRouter(prefix="/auth", tags=["authentication"])

# Google OAuth service for production
google_oauth = GoogleOAuthService()


def validate_redirect_url(url: str) -> bool:
    """
    Validate that the redirect URL is in the allowed list.

    Args:
        url: URL to validate

    Returns:
        True if URL is allowed, False otherwise
    """
    # Strip trailing slashes for comparison
    url_normalized = url.rstrip("/")

    for allowed_url in auth_settings.allowed_frontend_urls:
        allowed_normalized = allowed_url.strip().rstrip("/")
        if url_normalized == allowed_normalized or url_normalized.startswith(allowed_normalized + "/"):
            return True

    return False


@router.get("/login", response_model=LoginResponse)
async def login(redirect_to: Optional[str] = Query(None, description="URL to redirect to after login")):
    """
    Initiate Google OAuth2 login flow.

    Args:
        redirect_to: Optional URL to redirect to after successful login.
                     Must be in the allowed frontend URLs list.

    Returns:
        Authorization URL to redirect user to
    """
    # Validate redirect_to if provided
    if redirect_to and not validate_redirect_url(redirect_to):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid redirect URL. Must be one of: {', '.join(auth_settings.allowed_frontend_urls)}"
        )

    # Generate state for CSRF protection with optional redirect_to
    state_data = {
        "csrf": secrets.token_urlsafe(32),
        "redirect_to": redirect_to or auth_settings.allowed_frontend_urls[0]  # Default to first allowed URL
    }
    state = base64.urlsafe_b64encode(json.dumps(state_data).encode()).decode()

    if auth_settings.use_mocks and okta_mock:
        # Mock mode: return simplified URL (for backward compatibility)
        auth_url = okta_mock.get_authorization_url(
            redirect_uri=auth_settings.google_redirect_uri,
            state=state
        )
    else:
        # Production: Use Google OAuth
        auth_url = google_oauth.get_authorization_url(state=state)

    return LoginResponse(authorization_url=auth_url)


@router.get("/callback")
async def callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State parameter for CSRF protection")
):
    """
    Handle Google OAuth2 callback.

    Args:
        code: Authorization code from Google
        state: State parameter for CSRF protection (contains redirect_to URL)

    Returns:
        Redirect to frontend with session cookie set
    """
    try:
        # Decode state to get redirect URL
        try:
            state_data = json.loads(base64.urlsafe_b64decode(state))
            redirect_url = state_data.get("redirect_to", auth_settings.allowed_frontend_urls[0])
        except (json.JSONDecodeError, ValueError):
            # Fallback for old-style state (just CSRF token)
            redirect_url = auth_settings.allowed_frontend_urls[0]

        # Validate redirect URL
        if not validate_redirect_url(redirect_url):
            redirect_url = auth_settings.allowed_frontend_urls[0]
        if auth_settings.use_mocks and okta_mock:
            # Mock mode: use mock token exchange (for backward compatibility)
            token_response = okta_mock.exchange_code_for_token(
                code=code,
                redirect_uri=auth_settings.google_redirect_uri
            )
            # Use id_token as session token
            session_token = token_response["id_token"]
        else:
            # Production: Exchange code for token with Google
            token_response = await google_oauth.exchange_code_for_token(code)

            # Get ID token
            id_token = token_response.get("id_token")
            if not id_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No ID token received from Google"
                )

            # Verify ID token
            claims = google_oauth.verify_id_token(id_token)

            # Validate email domain
            email = claims.get("email")
            if not email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No email in token claims"
                )

            if not google_oauth.validate_email_domain(email):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Email domain not allowed. Must be {auth_settings.allowed_email_domain}"
                )

            # Use id_token as session token
            session_token = id_token

            # Check if this is the super admin and needs OAuth authorization
            if auth_settings.super_admin_email and email.lower() == auth_settings.super_admin_email.lower():
                from app.services.dt_token_service import dt_token_service

                dt_id = auth_settings.super_admin_dt_id
                if dt_id:
                    # Check if already authorized
                    status = await dt_token_service.get_authorization_status(dt_id)

                    if not status.get("authorized", False):
                        # Build the authorization URL with extended scopes
                        authorization_url = google_oauth.get_authorization_url(
                            redirect_uri=f"{auth_settings.backend_url}/auth/callback-dt",
                            scopes=auth_settings.dt_oauth_scopes,
                            access_type="offline",
                            prompt="consent",
                            state=email,
                        )

                        # Create redirect response to OAuth authorization
                        redirect_response = RedirectResponse(url=authorization_url, status_code=302)

                        # Set session cookie so user is authenticated when they return
                        redirect_response.set_cookie(
                            key=auth_settings.session_cookie_name,
                            value=session_token,
                            max_age=auth_settings.session_max_age,
                            httponly=True,
                            secure=False,  # Set to True in production with HTTPS
                            samesite="lax"
                        )

                        return redirect_response

        # Create redirect response with dynamic URL
        redirect_response = RedirectResponse(url=redirect_url)

        # Use SameSite=Lax for all environments
        # Frontend uses Vite proxy in dev, so requests are same-origin
        redirect_response.set_cookie(
            key=auth_settings.session_cookie_name,
            value=session_token,
            max_age=auth_settings.session_max_age,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax"
        )

        return redirect_response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authentication failed: {str(e)}"
        )


@router.post("/logout")
async def logout(response: Response):
    """
    Logout user by clearing session cookie.

    Args:
        response: FastAPI response object

    Returns:
        Success message
    """
    # Use SameSite=Lax for all environments (matches login cookie)
    response.delete_cookie(
        key=auth_settings.session_cookie_name,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax"
    )

    return {"message": "Logged out successfully"}


@router.get("/me", response_model=User)
async def get_me(current_user: Optional[User] = Depends(get_current_user)):
    """
    Get current authenticated user information.

    Args:
        current_user: Current user from session

    Returns:
        User information

    Raises:
        HTTPException: 401 if not authenticated
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    return current_user


@router.get("/mock-login")
async def mock_login(
    redirect_uri: str = Query(...),
    state: str = Query(...),
    email: str = Query("thomas.manson@croix-rouge.fr", description="Email to login as")
):
    """
    Mock login endpoint for development/testing.
    Simulates Google OAuth login by generating an authorization code.

    Args:
        redirect_uri: Callback URL
        state: State parameter
        email: Email to authenticate as (default: DT manager)

    Returns:
        Redirect to callback with authorization code
    """
    if not auth_settings.use_mocks or not okta_mock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mock login only available in mock mode"
        )

    # Generate authorization code
    code = okta_mock.create_mock_authorization_code(email)

    # Redirect to callback
    return RedirectResponse(url=f"{redirect_uri}?code={code}&state={state}")


# ============================================================================
# DT Manager OAuth Authorization Endpoints
# ============================================================================

@router.get("/authorize-dt")
async def authorize_dt(
    current_user: User = Depends(require_dt_manager)
):
    """
    Initiate OAuth flow for DT manager to authorize Calendar/Drive/Gmail access.
    Requires already being logged in as DT manager.

    Returns:
        Authorization URL with extended scopes
    """
    # Build authorization URL with extended scopes
    authorization_url = google_oauth.get_authorization_url(
        redirect_uri=f"{auth_settings.backend_url}/auth/callback-dt",
        scopes=auth_settings.dt_oauth_scopes,
        access_type="offline",  # For refresh token
        prompt="consent",  # Force consent to get refresh token
        state=current_user.email,  # Pass email in state for callback
    )
    return {"authorization_url": authorization_url}


@router.get("/callback-dt")
async def callback_dt(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="DT manager email from state"),
):
    """
    OAuth callback for DT manager authorization.
    Exchanges code for tokens and stores refresh token securely.

    Args:
        code: Authorization code from Google
        state: DT manager email passed in state parameter

    Returns:
        Redirect to admin app with success message
    """
    from app.services.dt_token_service import dt_token_service

    try:
        # Exchange code for tokens
        tokens = await google_oauth.exchange_code_for_tokens(
            code=code,
            redirect_uri=f"{auth_settings.backend_url}/auth/callback-dt",
        )

        if not tokens.get("refresh_token"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No refresh token received. Please revoke app access in Google settings and try again."
            )

        # Store tokens securely (encrypted with KMS)
        # Use super admin DT ID if the email matches, otherwise use default
        dt_id = "DT75"  # Default
        if auth_settings.super_admin_email and state.lower() == auth_settings.super_admin_email.lower():
            dt_id = auth_settings.super_admin_dt_id or "DT75"

        success = await dt_token_service.store_tokens(
            dt_id=dt_id,
            email=state,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            expires_in=tokens.get("expires_in", 3600),
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store tokens"
            )

        # Redirect to frontend
        # Use first allowed frontend URL
        frontend_url = auth_settings.allowed_frontend_urls[0]
        return RedirectResponse(
            url=frontend_url,
            status_code=302
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authorization failed: {str(e)}"
        )


@router.get("/dt-authorization-status")
async def get_dt_authorization_status(
    current_user: User = Depends(require_dt_manager)
):
    """
    Check if DT manager has authorized Calendar/Drive/Gmail access.

    Returns:
        Authorization status with email and timestamp
    """
    from app.services.dt_token_service import dt_token_service

    dt_id = "DT75"  # TODO: Get from user context
    status_data = await dt_token_service.get_authorization_status(dt_id)

    return {
        "authorized": status_data.get("authorized", False),
        "email": status_data.get("email"),
        "authorized_at": status_data.get("authorized_at"),
        "scopes": ["calendar", "drive", "gmail"] if status_data.get("authorized") else [],
    }


@router.post("/revoke-dt-authorization")
async def revoke_dt_authorization(
    current_user: User = Depends(require_dt_manager)
):
    """
    Revoke DT manager's Calendar/Drive/Gmail authorization.

    Returns:
        Success message
    """
    from app.services.dt_token_service import dt_token_service

    dt_id = "DT75"  # TODO: Get from user context
    success = await dt_token_service.revoke_tokens(dt_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke authorization"
        )

    return {"message": "Authorization revoked successfully"}

