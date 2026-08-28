"""
Configuration service for managing application configuration in Redis.
"""
import os
from typing import Dict, Any, Optional
from app.services.redis_service import RedisService
from app.models.redis_models import DTConfiguration


class ConfigService:
    """Service for managing configuration using RedisService."""

    def __init__(self, redis_service: RedisService):
        """
        Initialize the configuration service.

        Args:
            redis_service: RedisService instance
        """
        self.redis_service = redis_service

    async def get_config(self) -> Dict[str, Any]:
        """
        Get current configuration from Redis or environment variables.

        Returns:
            Dictionary with configuration values
        """
        # Try to get from Redis first
        dt_config = await self.redis_service.get_configuration()

        # Build config dict with fallback to environment variables
        config = {
            # ⚠️ Redis est la SEULE source du destinataire des alertes.
            #
            # Il y avait un repli sur `EMAIL_DESTINATAIRE_ALERTES`, et ce repli était
            # un piège : c'est un réglage MÉTIER, modifiable par un gestionnaire DT
            # depuis l'écran de configuration, pas un paramètre de déploiement.
            # Un environnement qui portait la variable écrasait silencieusement le
            # « rien » que l'écran affichait — et la valeur trouvée dans
            # `backend/.env` le 2026-08-28 était l'adresse personnelle d'un
            # prestataire externe, jamais choisie dans l'application.
            #
            # Le champ existe déjà dans `DTConfiguration`, `ConfigUpdate`,
            # `ConfigResponse` et l'écran admin : il n'y a rien à ajouter, seulement
            # ce repli à retirer.
            # `or ""` : le champ est Optional dans DTConfiguration, et ConfigResponse
            # attend un `str`. Sans cette conversion, une configuration existante sans
            # destinataire faisait échouer la construction de la réponse — donc un 400
            # sur un PATCH sans rapport, le routeur enveloppant toute exception.
            # C'est le rôle que jouait par accident le repli sur l'environnement.
            "email_destinataire_alertes": (
                (dt_config.email_destinataire_alertes if dt_config else None) or ""
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
        Update configuration in Redis.

        Args:
            updates: Dictionary with configuration updates (only non-None values)

        Returns:
            Updated configuration dictionary
        """
        # Get current configuration from Redis
        dt_config = await self.redis_service.get_configuration()

        # If no config exists, create a new one with DT info from RedisService
        if not dt_config:
            dt_config = DTConfiguration(
                dt=self.redis_service.dt,
                nom=f"Configuration {self.redis_service.dt}",
                gestionnaire_email=os.getenv("EMAIL_GESTIONNAIRE_DT", "")
            )

        # Update only provided values (exclude read-only email_gestionnaire_dt)
        for key, value in updates.items():
            if value is not None and key != "email_gestionnaire_dt" and hasattr(dt_config, key):
                setattr(dt_config, key, value)

        # Save to Redis
        await self.redis_service.set_configuration(dt_config)

        # Return current config as dict
        return await self.get_config()

