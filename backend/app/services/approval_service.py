"""Service for managing devis approval tokens stored in Valkey."""
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

APPROVAL_TTL_DAYS = 7


class ApprovalService:
    """Manages approval tokens for devis approval workflow."""

    def __init__(self, redis_client: Redis, dt: str):
        self.redis = redis_client
        self.dt = dt

    def _token_key(self, token: str) -> str:
        return f"{self.dt}:approbation:{token}"

    async def create_approval_token(
        self,
        immat: str,
        numero_dossier: str,
        devis_id: str,
        valideur_email: str,
    ) -> Dict[str, Any]:
        """Create a new approval token and store in Valkey with 7-day TTL."""
        token = str(uuid.uuid4())
        now = datetime.utcnow()
        expires_at = now + timedelta(days=APPROVAL_TTL_DAYS)

        token_data = {
            "token": token,
            "dt": self.dt,
            "immat": immat,
            "numero_dossier": numero_dossier,
            "devis_id": devis_id,
            "valideur_email": valideur_email,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "status": "pending",
            "commentaire": None,
        }

        key = self._token_key(token)
        import json
        await self.redis.set(key, json.dumps(token_data), ex=APPROVAL_TTL_DAYS * 86400)

        logger.info(f"Created approval token {token} for devis {devis_id} in dossier {numero_dossier}")
        return token_data

    async def invalidate_token(self, token: str) -> bool:
        """Invalidate an existing approval token by deleting its Valkey key."""
        key = self._token_key(token)
        deleted = await self.redis.delete(key)
        if deleted:
            logger.info(f"Invalidated approval token {token}")
        return bool(deleted)

    async def get_approval_data(self, token: str) -> Optional[Dict[str, Any]]:
        """Retrieve approval token data from Valkey."""
        key = self._token_key(token)
        raw = await self.redis.get(key)
        if not raw:
            return None

        import json
        data = json.loads(raw)

        # Check expiration
        expires_at = datetime.fromisoformat(data["expires_at"])
        if datetime.utcnow() > expires_at:
            return None

        return data

    async def submit_decision(
        self,
        token: str,
        decision: str,
        commentaire: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Submit an approval decision (approuve or refuse)."""
        data = await self.get_approval_data(token)
        if not data:
            return None

        data["status"] = decision
        data["decision_at"] = datetime.utcnow().isoformat()
        if commentaire:
            data["commentaire"] = commentaire

        key = self._token_key(token)
        import json
        # Keep remaining TTL
        ttl = await self.redis.ttl(key)
        if ttl > 0:
            await self.redis.set(key, json.dumps(data), ex=ttl)
        else:
            await self.redis.set(key, json.dumps(data), ex=APPROVAL_TTL_DAYS * 86400)

        logger.info(f"Decision '{decision}' submitted for token {token}")
        return data

