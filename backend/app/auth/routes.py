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
from .dependencies import get_current_user
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

        # Create redirect response with dynamic URL
        redirect_response = RedirectResponse(url=redirect_url)

        # Set session cookie
        redirect_response.set_cookie(
            key=auth_settings.session_cookie_name,
            value=session_token,
            max_age=auth_settings.session_max_age,
            httponly=True,
            secure=not auth_settings.use_mocks,  # HTTPS only in production
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
    response.delete_cookie(
        key=auth_settings.session_cookie_name,
        httponly=True,
        secure=not auth_settings.use_mocks,
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

