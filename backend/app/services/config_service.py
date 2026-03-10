"""
Configuration service for managing application configuration in Redis.
"""
import os
from typing import Dict, Any, Optional
from app.cache.redis_cache import RedisCache


class ConfigService:
    """Service for managing configuration in Redis."""

    REDIS_KEY = "clef:config"

    def __init__(self, cache: RedisCache):
        """
        Initialize the configuration service.

        Args:
            cache: RedisCache instance
        """
        self.cache = cache

    async def get_config(self) -> Dict[str, Any]:
        """
        Get current configuration from Redis or environment variables.

        Returns:
            Dictionary with configuration values
        """
        # Try to get from Redis first
        stored_config = await self.cache.get(self.REDIS_KEY)

        if not stored_config:
            # Initialize from environment variables
            stored_config = {}
        
        # Merge with environment variables (env vars as defaults)
        config = {
            "sheets_url_vehicules": stored_config.get(
                "sheets_url_vehicules",
                os.getenv("SHEETS_URL_VEHICULES", "")
            ),
            "sheets_url_benevoles": stored_config.get(
                "sheets_url_benevoles",
                os.getenv("SHEETS_URL_BENEVOLES", "")
            ),
            "sheets_url_responsables": stored_config.get(
                "sheets_url_responsables",
                os.getenv("SHEETS_URL_RESPONSABLES", "")
            ),
            "template_doc_url": stored_config.get(
                "template_doc_url",
                os.getenv("TEMPLATE_DOCUMENT_VEHICULE_URL", "")
            ),
            "email_destinataire_alertes": stored_config.get(
                "email_destinataire_alertes",
                os.getenv("EMAIL_DESTINATAIRE_ALERTES", "")
            ),
            "email_gestionnaire_dt": os.getenv("EMAIL_GESTIONNAIRE_DT", ""),
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
        # Get current config
        current_config = await self.get_config()

        # Update only provided values
        for key, value in updates.items():
            if value is not None and key != "email_gestionnaire_dt":
                # Don't allow updating email_gestionnaire_dt (read-only)
                current_config[key] = value

        # Save to Redis (exclude email_gestionnaire_dt which comes from env)
        config_to_store = {
            k: v for k, v in current_config.items()
            if k != "email_gestionnaire_dt"
        }

        # Store with no TTL (persistent)
        await self.cache.set(self.REDIS_KEY, config_to_store, ttl=None)

        return current_config

