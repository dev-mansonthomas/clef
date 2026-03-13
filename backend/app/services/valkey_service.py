"""Valkey service with multi-tenant DT prefixing."""
import json
import logging
from typing import Optional, List, Dict, Any, Set
from redis.asyncio import Redis
from app.models.valkey_models import VehicleData, BenevoleData, CarnetBordEntry, DTConfiguration

logger = logging.getLogger(__name__)


class ValkeyService:
    """
    Service for Valkey operations with automatic DT prefixing.
    
    All keys are prefixed with the DT identifier to ensure multi-tenant isolation.
    Key pattern: DT{id}:resource:identifier
    
    Examples:
        - DT75:vehicules:AB-123-CD
        - DT75:benevoles:123456
        - DT75:carnet:AB-123-CD:2024-01-15T10:30:00
    """
    
    def __init__(self, redis_client: Redis, dt: str):
        """
        Initialize Valkey service.
        
        Args:
            redis_client: Async Redis client
            dt: DT identifier (e.g., "DT75")
        """
        self.redis = redis_client
        self.dt = dt
    
    def _key(self, *parts: str) -> str:
        """
        Build a DT-prefixed key.
        
        Args:
            *parts: Key parts to join
            
        Returns:
            Prefixed key string
        """
        return f"{self.dt}:{':'.join(parts)}"
    
    # ========== Configuration ==========
    
    async def get_configuration(self) -> Optional[DTConfiguration]:
        """Get DT configuration."""
        data = await self.redis.get(self._key("configuration"))
        if not data:
            return None
        return DTConfiguration(**json.loads(data))
    
    async def set_configuration(self, config: DTConfiguration) -> bool:
        """Set DT configuration."""
        try:
            await self.redis.set(self._key("configuration"), config.model_dump_json())
            return True
        except Exception as e:
            logger.error(f"Error setting configuration for {self.dt}: {e}")
            return False
    
    # ========== Vehicles ==========
    
    async def get_vehicle(self, immat: str) -> Optional[VehicleData]:
        """Get vehicle by license plate."""
        data = await self.redis.get(self._key("vehicules", immat))
        if not data:
            return None
        return VehicleData(**json.loads(data))
    
    async def set_vehicle(self, vehicle: VehicleData) -> bool:
        """Set vehicle data and add to index."""
        try:
            key = self._key("vehicules", vehicle.immat)
            await self.redis.set(key, vehicle.model_dump_json())
            await self.redis.sadd(self._key("vehicules", "index"), vehicle.immat)
            return True
        except Exception as e:
            logger.error(f"Error setting vehicle {vehicle.immat} for {self.dt}: {e}")
            return False
    
    async def list_vehicles(self) -> List[str]:
        """List all vehicle license plates for this DT."""
        members = await self.redis.smembers(self._key("vehicules", "index"))
        return list(members) if members else []
    
    async def delete_vehicle(self, immat: str) -> bool:
        """Delete vehicle and remove from index."""
        try:
            await self.redis.delete(self._key("vehicules", immat))
            await self.redis.srem(self._key("vehicules", "index"), immat)
            return True
        except Exception as e:
            logger.error(f"Error deleting vehicle {immat} for {self.dt}: {e}")
            return False
    
    # ========== Bénévoles ==========
    
    async def get_benevole(self, nivol: str) -> Optional[BenevoleData]:
        """Get bénévole by NIVOL."""
        data = await self.redis.get(self._key("benevoles", nivol))
        if not data:
            return None
        return BenevoleData(**json.loads(data))
    
    async def set_benevole(self, benevole: BenevoleData) -> bool:
        """Set bénévole data and add to indices."""
        try:
            key = self._key("benevoles", benevole.nivol)
            await self.redis.set(key, benevole.model_dump_json())
            
            # Add to global index
            await self.redis.sadd(self._key("benevoles", "index"), benevole.nivol)
            
            # Add to UL-specific index if UL is specified
            if benevole.ul:
                await self.redis.sadd(
                    self._key("benevoles", "by_ul", benevole.ul),
                    benevole.nivol
                )
            
            return True
        except Exception as e:
            logger.error(f"Error setting benevole {benevole.nivol} for {self.dt}: {e}")
            return False
    
    async def list_benevoles(self, ul: Optional[str] = None) -> List[str]:
        """
        List bénévole NIVOLs for this DT.
        
        Args:
            ul: Optional UL filter
            
        Returns:
            List of NIVOL identifiers
        """
        if ul:
            members = await self.redis.smembers(self._key("benevoles", "by_ul", ul))
        else:
            members = await self.redis.smembers(self._key("benevoles", "index"))
        return list(members) if members else []

    async def delete_benevole(self, nivol: str) -> bool:
        """Delete bénévole and remove from indices."""
        try:
            # Get benevole to find UL
            benevole = await self.get_benevole(nivol)

            # Delete main record
            await self.redis.delete(self._key("benevoles", nivol))

            # Remove from global index
            await self.redis.srem(self._key("benevoles", "index"), nivol)

            # Remove from UL index if applicable
            if benevole and benevole.ul:
                await self.redis.srem(
                    self._key("benevoles", "by_ul", benevole.ul),
                    nivol
                )

            return True
        except Exception as e:
            logger.error(f"Error deleting benevole {nivol} for {self.dt}: {e}")
            return False

    # ========== Carnet de Bord ==========

    async def add_carnet_entry(self, entry: CarnetBordEntry) -> bool:
        """
        Add a carnet de bord entry.

        Key format: DT{id}:carnet:{immat}:{timestamp_iso}
        """
        try:
            timestamp_str = entry.timestamp.isoformat()
            key = self._key("carnet", entry.immat, timestamp_str)
            await self.redis.set(key, entry.model_dump_json())

            # Add to vehicle's carnet index
            await self.redis.sadd(
                self._key("carnet", entry.immat, "index"),
                timestamp_str
            )

            return True
        except Exception as e:
            logger.error(f"Error adding carnet entry for {entry.immat}: {e}")
            return False

    async def get_carnet_entries(
        self,
        immat: str,
        limit: Optional[int] = None
    ) -> List[CarnetBordEntry]:
        """
        Get carnet de bord entries for a vehicle.

        Args:
            immat: Vehicle license plate
            limit: Optional limit on number of entries (most recent first)

        Returns:
            List of carnet entries sorted by timestamp (newest first)
        """
        try:
            # Get all timestamps from index
            timestamps = await self.redis.smembers(
                self._key("carnet", immat, "index")
            )

            if not timestamps:
                return []

            # Sort timestamps in reverse order (newest first)
            sorted_timestamps = sorted(timestamps, reverse=True)

            # Apply limit if specified
            if limit:
                sorted_timestamps = sorted_timestamps[:limit]

            # Fetch entries
            entries = []
            for timestamp in sorted_timestamps:
                key = self._key("carnet", immat, timestamp)
                data = await self.redis.get(key)
                if data:
                    entries.append(CarnetBordEntry(**json.loads(data)))

            return entries
        except Exception as e:
            logger.error(f"Error getting carnet entries for {immat}: {e}")
            return []

    async def get_latest_carnet_entry(
        self,
        immat: str,
        entry_type: Optional[str] = None
    ) -> Optional[CarnetBordEntry]:
        """
        Get the latest carnet entry for a vehicle.

        Args:
            immat: Vehicle license plate
            entry_type: Optional filter by type ('Prise' or 'Retour')

        Returns:
            Latest carnet entry or None
        """
        entries = await self.get_carnet_entries(immat, limit=10)

        if entry_type:
            entries = [e for e in entries if e.type == entry_type]

        return entries[0] if entries else None

