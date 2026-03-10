"""API routers for CLEF."""

from .config import router as config_router
from .calendar import router as calendar_router

__all__ = ["config_router", "calendar_router"]

