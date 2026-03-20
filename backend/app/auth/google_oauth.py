"""
Google OAuth service for authentication.
"""
import secrets
from typing import Dict, Any
from urllib.parse import urlencode
from authlib.integrations.httpx_client import AsyncOAuth2Client
import httpx
from .config import auth_settings
import jwt
from jwt import PyJWKClient


class GoogleOAuthService:
    """Service for handling Google OAuth authentication."""

    def __init__(self):
        self.client_id = auth_settings.google_client_id
        self.client_secret = auth_settings.google_client_secret
        self.redirect_uri = auth_settings.google_redirect_uri
        self.auth_uri = auth_settings.google_auth_uri
        self.token_uri = auth_settings.google_token_uri
        self.userinfo_uri = auth_settings.google_userinfo_uri
        self.scopes = auth_settings.google_scopes

        # JWK client for verifying Google ID tokens (lazy initialization)
        self._jwks_client = None

    @property
    def jwks_client(self):
        """Lazy initialization of JWK client to avoid network calls during import."""
        if self._jwks_client is None:
            self._jwks_client = PyJWKClient("https://www.googleapis.com/oauth2/v3/certs")
        return self._jwks_client
    
    def get_authorization_url(
        self,
        state: str,
        redirect_uri: str = None,
        scopes: list[str] = None,
        access_type: str = "offline",
        prompt: str = "consent"
    ) -> str:
        """
        Generate Google OAuth authorization URL.

        Args:
            state: State parameter for CSRF protection
            redirect_uri: Optional custom redirect URI (defaults to self.redirect_uri)
            scopes: Optional custom scopes (defaults to self.scopes)
            access_type: "online" or "offline" (default: "offline" for refresh token)
            prompt: "none", "consent", "select_account" (default: "consent")

        Returns:
            Authorization URL to redirect user to
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri or self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes or self.scopes),
            "state": state,
            "access_type": access_type,
            "prompt": prompt
        }

        return f"{self.auth_uri}?{urlencode(params)}"
    
    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        
        Args:
            code: Authorization code from Google
            
        Returns:
            Token response containing access_token, id_token, etc.
        """
        async with AsyncOAuth2Client(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri
        ) as client:
            token = await client.fetch_token(
                self.token_uri,
                code=code,
                grant_type="authorization_code"
            )
            
            return token

    async def exchange_code_for_tokens(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access and refresh tokens.

        Args:
            code: Authorization code from Google
            redirect_uri: Redirect URI used in authorization request

        Returns:
            Token response containing access_token, refresh_token, id_token, etc.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_uri,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()
            return response.json()

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Use refresh token to get new access token.

        Args:
            refresh_token: Refresh token from previous authorization

        Returns:
            Token response containing new access_token and expires_in
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_uri,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get user information from Google using access token.
        
        Args:
            access_token: Access token from Google
            
        Returns:
            User information (email, name, etc.)
        """
        async with AsyncOAuth2Client(token={"access_token": access_token}) as client:
            response = await client.get(self.userinfo_uri)
            response.raise_for_status()
            return response.json()
    
    def verify_id_token(self, id_token: str) -> Dict[str, Any]:
        """
        Verify and decode Google ID token.
        
        Args:
            id_token: ID token from Google
            
        Returns:
            Decoded token claims
            
        Raises:
            jwt.InvalidTokenError: If token is invalid
        """
        # Get signing key from Google's JWK set
        signing_key = self.jwks_client.get_signing_key_from_jwt(id_token)
        
        # Verify and decode token
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=self.client_id,
            options={"verify_exp": True}
        )
        
        return claims
    
    def validate_email_domain(self, email: str) -> bool:
        """
        Validate that email belongs to allowed domain.

        Args:
            email: Email address to validate

        Returns:
            True if email domain is allowed, False otherwise
        """
        return email.lower().endswith(auth_settings.allowed_email_domain)

