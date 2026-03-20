"""
Service for managing DT Manager OAuth tokens with KMS encryption.
"""
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from app.services.kms_service import kms_service
from app.cache import get_cache

logger = logging.getLogger(__name__)


class DTTokenService:
    """Service for storing and retrieving DT Manager OAuth tokens."""
    
    def __init__(self):
        self.kms = kms_service
    
    def _get_token_key(self, dt_id: str) -> str:
        """Build Valkey key for DT tokens."""
        return f"{dt_id}:oauth:dt_manager_tokens"
    
    async def store_tokens(
        self,
        dt_id: str,
        email: str,
        access_token: str,
        refresh_token: str,
        expires_in: int = 3600,
    ) -> bool:
        """
        Store OAuth tokens for DT manager with KMS encryption.
        
        Args:
            dt_id: DT identifier (e.g., "DT75")
            email: DT manager email
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            expires_in: Token expiration in seconds
            
        Returns:
            True if stored successfully, False otherwise
        """
        try:
            cache = get_cache()
            if not cache._connected:
                await cache.connect()
            
            if not cache.client:
                logger.error("Redis client not available")
                return False
            
            # Encrypt tokens
            encrypted_access = self.kms.encrypt(access_token)
            encrypted_refresh = self.kms.encrypt(refresh_token)
            
            # Calculate expiration
            expires_at = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()
            
            # Store encrypted tokens
            token_data = {
                "email": email,
                "access_token": encrypted_access,
                "refresh_token": encrypted_refresh,
                "expires_at": expires_at,
                "authorized_at": datetime.utcnow().isoformat(),
            }
            
            key = self._get_token_key(dt_id)
            # Use regular set with JSON serialization for compatibility with fakeredis
            await cache.client.set(key, json.dumps(token_data))
            
            logger.info(f"Stored OAuth tokens for DT {dt_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing tokens for DT {dt_id}: {e}")
            return False
    
    async def get_access_token(self, dt_id: str) -> Optional[str]:
        """
        Get decrypted access token for DT manager.
        Automatically refreshes if expired.
        
        Args:
            dt_id: DT identifier
            
        Returns:
            Decrypted access token or None if not found/expired
        """
        try:
            cache = get_cache()
            if not cache._connected:
                await cache.connect()
            
            if not cache.client:
                return None
            
            key = self._get_token_key(dt_id)
            token_data_str = await cache.client.get(key)
            
            if not token_data_str:
                return None
            
            token_data = json.loads(token_data_str)
            
            # Check if token is expired
            expires_at = datetime.fromisoformat(token_data["expires_at"])
            if datetime.utcnow() >= expires_at:
                # Token expired, need to refresh
                logger.info(f"Access token expired for DT {dt_id}, refreshing...")
                refreshed = await self._refresh_token(dt_id, token_data)
                if not refreshed:
                    return None
                # Get updated token data
                token_data_str = await cache.client.get(key)
                if not token_data_str:
                    return None
                token_data = json.loads(token_data_str)
            
            # Decrypt and return access token
            encrypted_access = token_data["access_token"]
            return self.kms.decrypt(encrypted_access)
            
        except Exception as e:
            logger.error(f"Error getting access token for DT {dt_id}: {e}")
            return None
    
    async def _refresh_token(self, dt_id: str, token_data: Dict[str, Any]) -> bool:
        """
        Refresh access token using refresh token.
        
        Args:
            dt_id: DT identifier
            token_data: Current token data with encrypted refresh token
            
        Returns:
            True if refreshed successfully
        """
        try:
            from app.auth.google_oauth import GoogleOAuthService
            
            # Decrypt refresh token
            encrypted_refresh = token_data["refresh_token"]
            refresh_token = self.kms.decrypt(encrypted_refresh)
            
            # Use GoogleOAuthService to refresh
            oauth_service = GoogleOAuthService()
            new_tokens = await oauth_service.refresh_access_token(refresh_token)

            # Store new access token (keep same refresh token)
            await self.store_tokens(
                dt_id=dt_id,
                email=token_data["email"],
                access_token=new_tokens["access_token"],
                refresh_token=refresh_token,  # Reuse existing refresh token
                expires_in=new_tokens.get("expires_in", 3600),
            )

            return True

        except Exception as e:
            logger.error(f"Error refreshing token for DT {dt_id}: {e}")
            return False

    async def get_authorization_status(self, dt_id: str) -> Dict[str, Any]:
        """
        Check if DT manager has authorized OAuth access.

        Args:
            dt_id: DT identifier

        Returns:
            Dictionary with authorization status
        """
        try:
            cache = get_cache()
            if not cache._connected:
                await cache.connect()

            if not cache.client:
                return {"authorized": False}

            key = self._get_token_key(dt_id)
            token_data_str = await cache.client.get(key)

            if not token_data_str:
                return {"authorized": False}

            token_data = json.loads(token_data_str)

            return {
                "authorized": True,
                "email": token_data.get("email"),
                "authorized_at": token_data.get("authorized_at"),
            }

        except Exception as e:
            logger.error(f"Error checking authorization status for DT {dt_id}: {e}")
            return {"authorized": False}

    async def revoke_tokens(self, dt_id: str) -> bool:
        """
        Revoke OAuth tokens for DT manager.

        Args:
            dt_id: DT identifier

        Returns:
            True if revoked successfully
        """
        try:
            cache = get_cache()
            if not cache._connected:
                await cache.connect()

            if not cache.client:
                return False

            key = self._get_token_key(dt_id)
            await cache.client.delete(key)

            logger.info(f"Revoked OAuth tokens for DT {dt_id}")
            return True

        except Exception as e:
            logger.error(f"Error revoking tokens for DT {dt_id}: {e}")
            return False


# Singleton instance
dt_token_service = DTTokenService()


