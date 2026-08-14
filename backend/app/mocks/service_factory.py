"""Factory for creating Google API services (real or mock based on environment)."""
import os
import redis
from typing import Union, Optional

from .google_sheets_mock import GoogleSheetsMock
from .google_drive_mock import GoogleDriveMock
from .google_calendar_mock import GoogleCalendarMock
from .google_gmail_mock import GoogleGmailMock


def use_mocks() -> bool:
    """
    Check if mock services should be used.

    Returns:
        True if USE_MOCKS environment variable is set to 'true'
    """
    return os.getenv("USE_MOCKS", "false").lower() == "true"


#: Valeurs d'environnement considérées comme la production.
_PRODUCTION_ENVIRONMENTS = {"production", "prod"}


def assert_mocks_not_in_production() -> None:
    """Refuse le démarrage si les mocks sont actifs en production.

    Garde-fou du constat S1 (`docs/TODO.md`, critique). En mode mock,
    `get_current_user` accepte des JWT HS256 signés avec
    `mock-secret-key-for-testing` — un secret **présent en clair dans le dépôt**
    (`app/mocks/okta_mock.py:15`) : une session peut être forgée pour n'importe quel
    email, super admin compris. Le même drapeau réduit le chiffrement KMS à du base64
    (S2), exposant les refresh tokens OAuth stockés dans Redis.

    Le défaut (`"false"`) est sûr : cette fonction ajoute la défense en profondeur qui
    manquait, pour qu'un mauvais fichier d'environnement ne puisse pas partir en
    production silencieusement.

    Les **deux** variables sont inspectées : le dépôt lit `ENVIRONMENT`
    (`routers/api_keys.py`, `services/kms_service.py`) et `ENV` (`main.py`,
    `docker-compose.yml`). N'en garder qu'une laisserait une porte ouverte.

    Raises:
        RuntimeError: si `USE_MOCKS=true` et que l'environnement est la production.
    """
    if not use_mocks():
        return

    for var in ("ENVIRONMENT", "ENV"):
        value = os.getenv(var, "").strip().lower()
        if value in _PRODUCTION_ENVIRONMENTS:
            raise RuntimeError(
                f"Démarrage refusé : USE_MOCKS=true avec {var}={os.getenv(var)!r}. "
                "En mode mock, l'authentification accepte des jetons signés avec un "
                "secret public du dépôt et le chiffrement KMS est désactivé "
                "(docs/TODO.md S1, S2). Poser USE_MOCKS=false en production."
            )


def get_sheets_service():
    """
    Get Google Sheets service (real or mock).

    Returns:
        GoogleSheetsMock if USE_MOCKS=true, otherwise real service
    """
    # Use the new centralized factory from app.services.sheets
    from app.services.sheets import get_sheets_service as _get_sheets_service
    return _get_sheets_service()


def get_drive_service():
    """
    Get Google Drive service (real or mock).

    Returns:
        GoogleDriveMock if USE_MOCKS=true, otherwise real service
    """
    # Use the new centralized factory from app.services.drive
    from app.services.drive import get_drive_service as _get_drive_service
    return _get_drive_service()


def get_calendar_service(redis_client: Optional[redis.Redis] = None):
    """
    Get Google Calendar service (real or mock).

    Args:
        redis_client: Redis client for storing calendar IDs (optional)

    Returns:
        GoogleCalendarMock if USE_MOCKS=true, otherwise real CalendarService
    """
    if use_mocks():
        return GoogleCalendarMock()

    from app.services.calendar_service import CalendarService
    return CalendarService()


def get_gmail_service():
    """
    Get Gmail service (real or mock).

    Returns:
        GoogleGmailMock if USE_MOCKS=true, otherwise real service
    """
    if use_mocks():
        return GoogleGmailMock()

    from app.services.gmail_real import GoogleGmailService
    return GoogleGmailService()

