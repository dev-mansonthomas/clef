"""
Configuration for authentication module.
"""
import os
from typing import Annotated, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode


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
    google_scopes: Annotated[list[str], NoDecode] = ["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"]

    # Scopes for DT Manager authorization (Calendar + Drive + Gmail)
    dt_oauth_scopes: Annotated[list[str], NoDecode] = [
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

    # Destinations autorisées après connexion, séparées par des virgules.
    #
    # ⚠️ `NoDecode` n'est pas décoratif : sans lui, pydantic-settings exige du **JSON**
    # pour tout champ de type complexe lu depuis l'environnement. Une valeur comme
    # « https://clef-frontend-xxx.run.app » lève alors
    #
    #     SettingsError: error parsing value for field "allowed_frontend_urls"
    #     from source "EnvSettingsSource"
    #
    # ...à l'IMPORT du module, donc avant que l'application existe. C'est ce qui a
    # fait échouer le premier déploiement réel : le conteneur mourait au démarrage,
    # et le message de Cloud Run parlait d'une sonde, pas de configuration.
    #
    # Le piège est qu'en local la variable n'est jamais définie : la valeur par
    # défaut s'applique, rien ne plante, et aucun test ne couvrait le cas.
    #
    # ⚠️ Les entrées vides sont filtrées par le validateur ci-dessous, et ce n'est pas
    # cosmétique : une chaîne vide dégénère `validate_redirect_url` en
    # `url.startswith("/")`, qui accepte l'URL protocol-relative `//evil.tld` — soit
    # un open redirect. Le cas est atteignable, le script de déploiement rendant la
    # variable vide au tout premier passage.
    allowed_frontend_urls: Annotated[list[str], NoDecode] = [
        "http://localhost:4200",
        "http://localhost:4202",
    ]

    @field_validator(
        "allowed_frontend_urls", "google_scopes", "dt_oauth_scopes", mode="before"
    )
    @classmethod
    def _liste_separee_par_virgules(cls, v: object) -> object:
        """Accepte « a,b,c » là où pydantic-settings attendrait du JSON.

        Appliqué aux trois champs de type liste, pas seulement à celui qui a explosé :
        les deux autres n'étaient pas injectés, mais le jour où quelqu'un pose
        `GOOGLE_SCOPES` ou `DT_OAUTH_SCOPES` dans l'environnement, le défaut échouerait
        exactement de la même façon.
        """
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    # Backend URL for OAuth callbacks
    backend_url: str = os.getenv("BACKEND_URL", "http://localhost:8000")

    # ⚠️ Le flux DT doit partir de la MÊME ORIGINE que le flux principal.
    #
    # Les trois points d'appel de `/auth/authorize-dt` fabriquaient leur URI de
    # redirection avec `f"{backend_url}/auth/callback-dt"`, donc l'URL *.run.app du
    # service — alors que le flux principal annonce `GOOGLE_REDIRECT_URI`, soit le
    # domaine public. Deux origines pour un seul client OAuth : il faut alors DEUX
    # URI déclarés en console, et celui du DT casse le jour où l'ingress est
    # verrouillé sur le load balancer (l'URL run.app cesse d'être joignable).
    #
    # Le load balancer route `/auth/*` vers l'API : le domaine public convient donc
    # aux deux. Le défaut reste dérivé de `backend_url` pour le développement local.
    dt_oauth_redirect_uri: str = os.getenv(
        "DT_OAUTH_REDIRECT_URI",
        f"{os.getenv('BACKEND_URL', 'http://localhost:8000')}/auth/callback-dt",
    )

    class Config:
        # ⚠️ `.env.local` — la configuration de CE POSTE, jamais celle d'un
        # environnement déployé. Renommé depuis `.env` le 2026-08-28 pour lever
        # l'ambiguïté avec `.env.dev` / `.env.test` / `.env.prod`, qui décrivent les
        # cibles de déploiement. Sur Cloud Run, aucun de ces fichiers n'est lu : les
        # variables viennent du gabarit et les secrets de Secret Manager.
        env_file = ".env.local"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


# Global settings instance
auth_settings = AuthSettings()

