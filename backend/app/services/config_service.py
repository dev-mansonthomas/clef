"""
Configuration service for managing application configuration in Valkey.
"""
import os
from typing import Dict, Any, Optional
from app.services.valkey_service import ValkeyService
from app.models.valkey_models import DTConfiguration


class ConfigService:
    """Service for managing configuration using ValkeyService."""

    def __init__(self, valkey_service: ValkeyService):
        """
        Initialize the configuration service.

        Args:
            valkey_service: ValkeyService instance
        """
        self.valkey_service = valkey_service

    async def get_config(self) -> Dict[str, Any]:
        """
        Get current configuration from Valkey or environment variables.

        Returns:
            Dictionary with configuration values
        """
        # Try to get from Valkey first
        dt_config = await self.valkey_service.get_configuration()

        # Build config dict with fallback to environment variables
        config = {
            "email_destinataire_alertes": (
                dt_config.email_destinataire_alertes if dt_config and dt_config.email_destinataire_alertes
                else os.getenv("EMAIL_DESTINATAIRE_ALERTES", "")
            ),
            "email_gestionnaire_dt": os.getenv("EMAIL_GESTIONNAIRE_DT", ""),
            "drive_folder_id": dt_config.drive_folder_id if dt_config else None,
            "drive_folder_url": dt_config.drive_folder_url if dt_config else None,
            "drive_sync_status": dt_config.drive_sync_status if dt_config else "idle",
            "drive_sync_processed": dt_config.drive_sync_processed if dt_config else 0,
            "drive_sync_total": dt_config.drive_sync_total if dt_config else 0,
            "drive_sync_message": dt_config.drive_sync_message if dt_config else None,
            "drive_sync_error": dt_config.drive_sync_error if dt_config else None,
            "drive_sync_current_vehicle": dt_config.drive_sync_current_vehicle if dt_config else None,
        }

        return config
    
    async def update_config(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update configuration in Valkey.

        Args:
            updates: Dictionary with configuration updates (only non-None values)

        Returns:
            Updated configuration dictionary
        """
        # Get current configuration from Valkey
        dt_config = await self.valkey_service.get_configuration()

        # If no config exists, create a new one with DT info from ValkeyService
        if not dt_config:
            dt_config = DTConfiguration(
                dt=self.valkey_service.dt,
                nom=f"Configuration {self.valkey_service.dt}",
                gestionnaire_email=os.getenv("EMAIL_GESTIONNAIRE_DT", "")
            )

        # Update only provided values (exclude read-only email_gestionnaire_dt)
        for key, value in updates.items():
            if value is not None and key != "email_gestionnaire_dt" and hasattr(dt_config, key):
                setattr(dt_config, key, value)

        # Save to Valkey
        await self.valkey_service.set_configuration(dt_config)

        # Return current config as dict
        return await self.get_config()

