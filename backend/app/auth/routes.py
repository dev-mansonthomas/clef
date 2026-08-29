"""
Authentication routes for Google OAuth SSO.
"""
import base64
import json
import logging
import secrets
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Response, Query, Depends
from fastapi.responses import RedirectResponse
from .models import User, LoginResponse
from .config import auth_settings
from .dependencies import (
    get_current_user,
    require_dt_manager,
    require_dt_manager_or_super_admin,
)
from .oauth_state import consommer_nonce, creer_nonce
from .google_oauth import GoogleOAuthService
from .mock_instance import okta_mock


logger = logging.getLogger(__name__)

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
                    # ⚠️ Ne pas nommer cette variable `status` : elle masquerait le
                    # module `fastapi.status` importé en tête, et le gestionnaire
                    # d'exception en fin de fonction lèverait alors un AttributeError
                    # au lieu de son 400.
                    statut_autorisation = await dt_token_service.get_authorization_status(dt_id)

                    if not statut_autorisation.get("authorized", False):
                        # Même correctif que /auth/authorize-dt : un nonce, pas l'email.
                        # C'était le second point d'entrée du parcours vulnérable (C4).
                        nonce = await creer_nonce(email, dt_id)

                        authorization_url = google_oauth.get_authorization_url(
                            redirect_uri=auth_settings.dt_oauth_redirect_uri,
                            scopes=auth_settings.dt_oauth_scopes,
                            access_type="offline",
                            prompt="consent",
                            state=nonce,
                        )

                        # Create redirect response to OAuth authorization
                        redirect_response = RedirectResponse(url=authorization_url, status_code=302)

                        # Set session cookie so user is authenticated when they return
                        redirect_response.set_cookie(
                            key=auth_settings.session_cookie_name,
                            value=session_token,
                            max_age=auth_settings.session_max_age,
                            httponly=True,
                            # Piloté par SESSION_COOKIE_SECURE : `true` sur Cloud Run (HTTPS),
                            # `false` en développement local (HTTP).
                            secure=auth_settings.session_cookie_secure,
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
            # Piloté par SESSION_COOKIE_SECURE : `true` sur Cloud Run (HTTPS),
            # `false` en développement local (HTTP).
            secure=auth_settings.session_cookie_secure,
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
    # ⚠️ Les attributs doivent être IDENTIQUES à ceux de la pose : un navigateur
    # identifie un cookie par (nom, domaine, chemin) mais refuse de supprimer un
    # cookie Secure via une instruction non Secure. Un `secure` divergent ici et la
    # déconnexion ne déconnecte pas.
    response.delete_cookie(
        key=auth_settings.session_cookie_name,
        httponly=True,
        secure=auth_settings.session_cookie_secure,
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
    # ⚠️ `state` est un NONCE, jamais une identité — constat C4. Il porte côté serveur
    # l'email de l'initiateur et sa délégation ; le rappel les y relit. Mettre l'email
    # dans l'URL laissait n'importe qui se déclarer gestionnaire au retour.
    nonce = await creer_nonce(current_user.email, current_user.dt)

    authorization_url = google_oauth.get_authorization_url(
        redirect_uri=auth_settings.dt_oauth_redirect_uri,
        scopes=auth_settings.dt_oauth_scopes,
        access_type="offline",  # For refresh token
        prompt="consent",  # Force consent to get refresh token
        state=nonce,
    )
    return {"authorization_url": authorization_url}


@router.get("/callback-dt")
async def callback_dt(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="Nonce émis par le serveur au lancement"),
    current_user: User = Depends(require_dt_manager_or_super_admin),
):
    """Retour du consentement étendu du gestionnaire DT (Calendar, Drive, Gmail).

    **Constat C4.** Cette route n'avait aucun guard et prenait l'identité du
    gestionnaire dans `state`, un paramètre d'URL non signé. Le `client_id` étant public
    et le `redirect_uri` déclaré en console, n'importe qui pouvant consentir construisait
    l'URL Google lui-même, consentait avec **son** compte, et rejouait le retour avec
    l'email d'un gestionnaire : son jeton de rafraîchissement devenait l'identité
    déléguée de la délégation, écrasant le légitime. Les documents déposés par les
    bénévoles partaient dès lors dans son Drive, et CLEF envoyait des courriels sous son
    compte.

    Quatre contrôles, dans cet ordre — chacun refuse ce que le précédent laisse passer :

    1. **session** — `require_dt_manager_or_super_admin` : sans session, il n'y a
       personne à qui rattacher un consentement ;
    2. **nonce** — `state` doit être un nonce que *nous* avons émis, vivant, et à usage
       unique. Il porte l'initiateur et la délégation visée ;
    3. **identité Google** — l'email vient de l'`id_token` **signé**, jamais de l'URL, et
       son domaine est contrôlé (ce que `/auth/callback` faisait déjà, pas celui-ci) ;
    4. **concordance** — l'email qui a consenti chez Google doit être celui de la session
       qui a lancé le parcours.

    La délégation de destination vient du **nonce**, donc du serveur : le `dt_id = "DT75"`
    codé en dur a disparu.

    ⚠️ Aucune branche `USE_MOCKS` ici, volontairement : le double d'Okta ne produit pas
    de jeton de rafraîchissement Google, et fabriquer une identité en mode mock sur la
    route même qui vient d'être durcie serait un contresens. Les tests substituent le
    client Google.

    Returns:
        Redirection vers l'application d'administration.
    """
    from app.services.dt_token_service import dt_token_service

    # 2 — le nonce. Lu et supprimé d'un seul geste : un nonce rejouable n'en est pas un.
    contexte = await consommer_nonce(state)
    if not contexte:
        logger.warning(
            "Consentement DT refusé : state invalide ou expiré (utilisateur=%s)",
            current_user.email,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Paramètre state invalide ou expiré : relancez l'autorisation",
        )

    # 4a — le nonce appartient-il à cette session ? Cas d'un nonce d'autrui rejoué.
    if contexte.get("email", "").lower() != current_user.email.lower():
        logger.warning(
            "Consentement DT refusé : nonce émis pour %s, présenté par %s",
            contexte.get("email"), current_user.email,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce parcours d'autorisation n'a pas été lancé par vous",
        )

    dt_id = contexte.get("dt")
    if not dt_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune délégation associée à ce parcours d'autorisation",
        )

    try:
        tokens = await google_oauth.exchange_code_for_tokens(
            code=code,
            redirect_uri=auth_settings.dt_oauth_redirect_uri,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Échange du code de consentement DT impossible : %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authorization failed: {e}",
        )

    # 3 — l'identité vient de Google, signée. C'est tout l'objet du correctif.
    id_token = tokens.get("id_token")
    if not id_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No ID token received from Google",
        )

    try:
        claims = google_oauth.verify_id_token(id_token)
    except Exception as e:
        logger.warning("id_token du consentement DT invalide : %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Identité Google invalide",
        )

    email_google = (claims.get("email") or "").strip()
    if not email_google or not google_oauth.validate_email_domain(email_google):
        logger.warning(
            "Consentement DT refusé : domaine non autorisé (utilisateur=%s)",
            current_user.email,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Email domain not allowed. Must be "
                f"{auth_settings.allowed_email_domain}"
            ),
        )

    # 4b — le compte qui a consenti est-il celui de la session ?
    if email_google.lower() != current_user.email.lower():
        logger.warning(
            "Consentement DT refusé : consenti par %s, session de %s",
            email_google, current_user.email,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Le compte Google qui a consenti n'est pas celui de votre session",
        )

    if not tokens.get("refresh_token"):
        # Google n'en renvoie pas quand l'accès est déjà accordé. Sans jeton de
        # rafraîchissement, la délégation ne survivrait pas à l'heure qui vient.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No refresh token received. Please revoke app access in Google "
                "settings and try again."
            ),
        )

    stocke = await dt_token_service.store_tokens(
        dt_id=dt_id,
        email=email_google,
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        expires_in=tokens.get("expires_in", 3600),
    )
    if not stocke:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store tokens",
        )

    logger.info("Consentement Google enregistré pour %s (%s)", dt_id, email_google)
    return RedirectResponse(url=auth_settings.allowed_frontend_urls[0], status_code=302)


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

    # La délégation vient de l'utilisateur. Laisser « DT75 » ici rendrait ce statut
    # incohérent avec `/auth/callback-dt`, qui enregistre désormais le consentement sur
    # la délégation portée par le nonce.
    status_data = await dt_token_service.get_authorization_status(current_user.dt)

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

    # Même raison qu'au-dessus : révoquer DT75 depuis la session d'une autre
    # délégation serait une révocation croisée.
    success = await dt_token_service.revoke_tokens(current_user.dt)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke authorization"
        )

    return {"message": "Authorization revoked successfully"}

