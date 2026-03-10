"""
Configuration for authentication module.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class AuthSettings(BaseSettings):
    """Authentication settings loaded from environment variables."""
    
    # Okta configuration
    okta_domain: str = os.getenv("OKTA_DOMAIN", "croix-rouge.okta.com")
    okta_client_id: str = os.getenv("OKTA_CLIENT_ID", "")
    okta_client_secret: str = os.getenv("OKTA_CLIENT_SECRET", "")
    okta_redirect_uri: str = os.getenv("OKTA_REDIRECT_URI", "http://localhost:8000/auth/callback")
    okta_issuer: str = os.getenv("OKTA_ISSUER", "https://croix-rouge.okta.com/oauth2/default")
    
    # DT Manager email
    email_gestionnaire_dt: str = os.getenv("EMAIL_GESTIONNAIRE_DT", "thomas.manson@croix-rouge.fr")
    
    # Session configuration
    session_secret_key: str = os.getenv("SESSION_SECRET_KEY", "dev-secret-key-change-in-production")
    session_cookie_name: str = "clef_session"
    session_max_age: int = 3600 * 24  # 24 hours
    
    # Mock mode
    use_mocks: bool = os.getenv("USE_MOCKS", "false").lower() == "true"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


# Global settings instance
auth_settings = AuthSettings()

