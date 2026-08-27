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

    # Scopes for DT Manager authorization (Calendar + Drive + Gmail)
    dt_oauth_scopes: list[str] = [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/gmail.send",
    ]

    # Email domain validation
    allowed_email_domain: str = "@croix-rouge.fr"

    # DT Manager email
    email_gestionnaire_dt: str = os.getenv("EMAIL_GESTIONNAIRE_DT", "thomas.manson@croix-rouge.fr")

    # Super Admin Configuration
    super_admin_email: str = os.getenv("SUPER_ADMIN_EMAIL", "")
    super_admin_dt_id: str = os.getenv("SUPER_ADMIN_DT_ID", "")
    super_admin_dt_numeric_id: str = os.getenv("SUPER_ADMIN_DT_NUMERIC_ID", "")

    # Session configuration
    session_secret_key: str = os.getenv("SESSION_SECRET_KEY", "dev-secret-key-change-in-production")
    session_cookie_name: str = "clef_session"

    # Le cookie doit porter l'attribut Secure dès que le site est servi en HTTPS,
    # sinon un navigateur l'accepte mais le transmettrait aussi en clair. Défaut
    # `false` pour le développement local, qui tourne en HTTP.
    #
    # `SameSite=Lax` reste correct en production : nginx relaie /api et /auth, donc
    # frontend et backend sont la MÊME origine vue du navigateur. Ce serait faux
    # avec un apiUrl absolu — il faudrait alors `SameSite=None; Secure`.
    session_cookie_secure: bool = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    session_max_age: int = 3600 * 24  # 24 hours

    # Mock mode
    use_mocks: bool = os.getenv("USE_MOCKS", "false").lower() == "true"

    # Délégation par défaut.
    #
    # ⚠️ Couture du multi-DT (décision D2). L'authentification ne connaît pas la
    # délégation de l'utilisateur *avant* de l'avoir cherché dans le référentiel :
    # elle interroge donc celle-ci. Une seule délégation existe aujourd'hui (DT75).
    # Le jour où une deuxième arrive, c'est ici qu'il faudra un index global
    # email → DT, et non un défaut. Ce champ existe pour que ce point unique soit
    # nommé et cherchable, plutôt que dispersé en littéraux "DT75".
    default_dt: str = os.getenv("DEFAULT_DT", "DT75")

    # Destinations autorisées après connexion (séparées par des virgules).
    #
    # ⚠️ Les entrées vides sont filtrées, et ce n'est pas cosmétique : une chaîne
    # vide dans cette liste dégénère `validate_redirect_url` en
    # `url.startswith("/")`, qui accepte alors l'URL protocol-relative `//evil.tld`
    # — soit un open redirect. Le cas est atteignable : le script de déploiement
    # rend la variable vide au tout premier déploiement, avant que l'URL du service
    # n'existe.
    allowed_frontend_urls: list[str] = [
        u.strip()
        for u in os.getenv(
            "ALLOWED_FRONTEND_URLS",
            "http://localhost:4200,http://localhost:4202"
        ).split(",")
        if u.strip()
    ]

    # Backend URL for OAuth callbacks
    backend_url: str = os.getenv("BACKEND_URL", "http://localhost:8000")

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


# Global settings instance
auth_settings = AuthSettings()

