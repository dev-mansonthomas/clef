"""
Shared mock instance for authentication testing.
This ensures the same mock secret is used across all modules.
"""
from .config import auth_settings
from app.mocks.okta_mock import OktaMock


# Shared mock instance (only created once)
okta_mock = OktaMock() if auth_settings.use_mocks else None

