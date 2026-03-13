"""API routers for CLEF."""

from .config import router as config_router
from .calendar import router as calendar_router
from .unites_locales import router as unites_locales_router

__all__ = ["config_router", "calendar_router", "unites_locales_router"]

