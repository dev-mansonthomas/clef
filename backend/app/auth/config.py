"""
Configuration for authentication module.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class AuthSettings(BaseSettings):
    """Authentication settings loaded from environment variables."""

    # Google OAuth configuration
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    google_redirect_uri: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback")

    # Google OAuth endpoints
    google_auth_uri: str = "https://accounts.google.com/o/oauth2/v2/auth"
    google_token_uri: str = "https://oauth2.googleapis.com/token"
    google_userinfo_uri: str = "https://www.googleapis.com/oauth2/v3/userinfo"

    # OAuth scopes
    google_scopes: list[str] = ["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"]

    # Email domain validation
    allowed_email_domain: str = "@croix-rouge.fr"

    # DT Manager email
    email_gestionnaire_dt: str = os.getenv("EMAIL_GESTIONNAIRE_DT", "thomas.manson@croix-rouge.fr")

    # Session configuration
    session_secret_key: str = os.getenv("SESSION_SECRET_KEY", "dev-secret-key-change-in-production")
    session_cookie_name: str = "clef_session"
    session_max_age: int = 3600 * 24  # 24 hours

    # Mock mode
    use_mocks: bool = os.getenv("USE_MOCKS", "false").lower() == "true"

    # Allowed frontend URLs for redirect (comma-separated)
    allowed_frontend_urls: list[str] = os.getenv(
        "ALLOWED_FRONTEND_URLS",
        "http://localhost:4200,http://localhost:4202"
    ).split(",")

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


# Global settings instance
auth_settings = AuthSettings()

