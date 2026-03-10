"""
Authentication routes for Okta SSO.
"""
import secrets
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Response, Query, Depends
from fastapi.responses import RedirectResponse
from .models import User, LoginResponse
from .config import auth_settings
from .dependencies import get_current_user
from app.mocks.okta_mock import OktaMock


router = APIRouter(prefix="/auth", tags=["authentication"])

# Mock Okta service for development
okta_mock = OktaMock() if auth_settings.use_mocks else None


@router.get("/login", response_model=LoginResponse)
async def login():
    """
    Initiate Okta OAuth2 login flow.
    
    Returns:
        Authorization URL to redirect user to
    """
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    
    if auth_settings.use_mocks and okta_mock:
        # Mock mode: return simplified URL
        auth_url = okta_mock.get_authorization_url(
            redirect_uri=auth_settings.okta_redirect_uri,
            state=state
        )
    else:
        # TODO: Implement real Okta authorization URL generation
        raise NotImplementedError("Real Okta integration not yet implemented")
    
    return LoginResponse(authorization_url=auth_url)


@router.get("/callback")
async def callback(
    code: str = Query(..., description="Authorization code from Okta"),
    state: str = Query(..., description="State parameter for CSRF protection")
):
    """
    Handle Okta OAuth2 callback.

    Args:
        code: Authorization code from Okta
        state: State parameter for CSRF protection

    Returns:
        Redirect to frontend with session cookie set
    """
    try:
        if auth_settings.use_mocks and okta_mock:
            # Exchange code for token
            token_response = okta_mock.exchange_code_for_token(
                code=code,
                redirect_uri=auth_settings.okta_redirect_uri
            )

            # Use id_token as session token
            session_token = token_response["id_token"]
        else:
            # TODO: Implement real Okta token exchange
            raise NotImplementedError("Real Okta integration not yet implemented")

        # Create redirect response
        redirect_response = RedirectResponse(url="http://localhost:4200/")

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
    Simulates Okta login by generating an authorization code.

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

