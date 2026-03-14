"""Valkey service with multi-tenant DT prefixing."""
import json
import logging
import uuid
import secrets
from typing import Optional, List, Dict, Any, Set
from datetime import datetime, date
from redis.asyncio import Redis
from app.models.valkey_models import VehicleData, BenevoleData, ResponsableData, ResponsableVehiculeData, CarnetBordEntry, DTConfiguration
from app.models.reservation import ValkeyReservation, ValkeyReservationCreate

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

    # ========== API Keys ==========

    async def generate_api_key_dt(self, name: str, created_by: str) -> Dict[str, Any]:
        """
        Generate and store a new API key for DT level.

        Args:
            name: Name/description of the API key
            created_by: Email of the user creating the key

        Returns:
            Dictionary with the new API key data including the full key
        """
        key = f"clef_sk_{secrets.token_hex(16)}"
        api_key_data = {
            "id": str(uuid.uuid4()),
            "name": name,
            "key": key,
            "created_at": datetime.utcnow().isoformat(),
            "created_by": created_by,
            "last_used": None
        }

        # Get current config
        config_data = await self.redis.get(self._key("configuration"))
        config = json.loads(config_data) if config_data else {}

        # Add API key to config
        if "api_keys" not in config:
            config["api_keys"] = []
        config["api_keys"].append(api_key_data)

        # Save updated config
        await self.redis.set(self._key("configuration"), json.dumps(config))

        return api_key_data

    async def generate_api_key_ul(self, ul_id: str, name: str, created_by: str) -> Dict[str, Any]:
        """
        Generate and store a new API key for UL level.

        Args:
            ul_id: UL identifier
            name: Name/description of the API key
            created_by: Email of the user creating the key

        Returns:
            Dictionary with the new API key data including the full key
        """
        key = f"clef_sk_{secrets.token_hex(16)}"
        api_key_data = {
            "id": str(uuid.uuid4()),
            "name": name,
            "key": key,
            "created_at": datetime.utcnow().isoformat(),
            "created_by": created_by,
            "last_used": None
        }

        # Get current UL data
        ul_data_raw = await self.redis.get(self._key("unite_locale", ul_id))
        if not ul_data_raw:
            raise ValueError(f"UL {ul_id} not found")

        ul_data = json.loads(ul_data_raw)

        # Add API key to UL data
        if "api_keys" not in ul_data:
            ul_data["api_keys"] = []
        ul_data["api_keys"].append(api_key_data)

        # Save updated UL data
        await self.redis.set(self._key("unite_locale", ul_id), json.dumps(ul_data))

        return api_key_data

    async def validate_api_key(self, key: str, ul_id: Optional[str] = None) -> bool:
        """
        Validate an API key (DT level or UL level).

        Args:
            key: The API key to validate
            ul_id: Optional UL identifier. If provided, validates UL-level key.
                   If None, validates DT-level key.

        Returns:
            True if key is valid, False otherwise
        """
        if ul_id:
            # Validate UL-level key
            ul_data_raw = await self.redis.get(self._key("unite_locale", ul_id))
            if not ul_data_raw:
                return False

            ul_data = json.loads(ul_data_raw)
            api_keys = ul_data.get("api_keys", [])

            for api_key in api_keys:
                if api_key["key"] == key:
                    # Update last_used timestamp
                    api_key["last_used"] = datetime.utcnow().isoformat()
                    await self.redis.set(self._key("unite_locale", ul_id), json.dumps(ul_data))
                    return True
            return False
        else:
            # Validate DT-level key
            config_data = await self.redis.get(self._key("configuration"))
            if not config_data:
                return False

            config = json.loads(config_data)
            api_keys = config.get("api_keys", [])

            for api_key in api_keys:
                if api_key["key"] == key:
                    # Update last_used timestamp
                    api_key["last_used"] = datetime.utcnow().isoformat()
                    await self.redis.set(self._key("configuration"), json.dumps(config))
                    return True
            return False

    async def list_api_keys_dt(self, mask_keys: bool = True) -> List[Dict[str, Any]]:
        """
        List all API keys for DT level.

        Args:
            mask_keys: If True, mask the key values for security

        Returns:
            List of API key dictionaries
        """
        config_data = await self.redis.get(self._key("configuration"))
        if not config_data:
            return []

        config = json.loads(config_data)
        api_keys = config.get("api_keys", [])

        if mask_keys:
            return [
                {**key, "key": f"clef_sk_{'●' * 16}"}
                for key in api_keys
            ]
        return api_keys

    async def list_api_keys_ul(self, ul_id: str, mask_keys: bool = True) -> List[Dict[str, Any]]:
        """
        List all API keys for UL level.

        Args:
            ul_id: UL identifier
            mask_keys: If True, mask the key values for security

        Returns:
            List of API key dictionaries
        """
        ul_data_raw = await self.redis.get(self._key("unite_locale", ul_id))
        if not ul_data_raw:
            return []

        ul_data = json.loads(ul_data_raw)
        api_keys = ul_data.get("api_keys", [])

        if mask_keys:
            return [
                {**key, "key": f"clef_sk_{'●' * 16}"}
                for key in api_keys
            ]
        return api_keys

    async def delete_api_key_dt(self, key_id: str) -> bool:
        """
        Delete an API key at DT level.

        Args:
            key_id: ID of the API key to delete

        Returns:
            True if deleted, False if not found
        """
        config_data = await self.redis.get(self._key("configuration"))
        if not config_data:
            return False

        config = json.loads(config_data)
        api_keys = config.get("api_keys", [])

        # Filter out the key to delete
        new_keys = [key for key in api_keys if key["id"] != key_id]

        if len(new_keys) == len(api_keys):
            return False  # Key not found

        config["api_keys"] = new_keys
        await self.redis.set(self._key("configuration"), json.dumps(config))
        return True

    async def delete_api_key_ul(self, ul_id: str, key_id: str) -> bool:
        """
        Delete an API key at UL level.

        Args:
            ul_id: UL identifier
            key_id: ID of the API key to delete

        Returns:
            True if deleted, False if not found
        """
        ul_data_raw = await self.redis.get(self._key("unite_locale", ul_id))
        if not ul_data_raw:
            return False

        ul_data = json.loads(ul_data_raw)
        api_keys = ul_data.get("api_keys", [])

        # Filter out the key to delete
        new_keys = [key for key in api_keys if key["id"] != key_id]

        if len(new_keys) == len(api_keys):
            return False  # Key not found

        ul_data["api_keys"] = new_keys
        await self.redis.set(self._key("unite_locale", ul_id), json.dumps(ul_data))
        return True

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

    async def get_vehicle_by_nom_synthetique(self, nom_synthetique: str) -> Optional[VehicleData]:
        """
        Get vehicle by synthetic name.

        Args:
            nom_synthetique: Synthetic name of the vehicle

        Returns:
            VehicleData or None if not found
        """
        # Get all vehicle IDs and search for matching nom_synthetique
        vehicle_ids = await self.list_vehicles()
        for immat in vehicle_ids:
            vehicle = await self.get_vehicle(immat)
            if vehicle and vehicle.nom_synthetique == nom_synthetique:
                return vehicle
        return None

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

    # ========== Responsables ==========

    async def get_responsable(self, email: str) -> Optional[ResponsableData]:
        """Get responsable by email."""
        data = await self.redis.get(self._key("responsables", email))
        if not data:
            return None
        return ResponsableData(**json.loads(data))

    async def set_responsable(self, responsable: ResponsableData) -> bool:
        """Set responsable data and add to index."""
        try:
            key = self._key("responsables", responsable.email)
            await self.redis.set(key, responsable.model_dump_json())

            # Add to global index
            await self.redis.sadd(self._key("responsables", "index"), responsable.email)

            return True
        except Exception as e:
            logger.error(f"Error setting responsable {responsable.email} for {self.dt}: {e}")
            return False

    async def list_responsables(self) -> List[str]:
        """List all responsable emails for this DT."""
        members = await self.redis.smembers(self._key("responsables", "index"))
        return list(members) if members else []

    async def delete_responsable(self, email: str) -> bool:
        """Delete responsable and remove from index."""
        try:
            await self.redis.delete(self._key("responsables", email))
            await self.redis.srem(self._key("responsables", "index"), email)
            return True
        except Exception as e:
            logger.error(f"Error deleting responsable {email} for {self.dt}: {e}")
            return False

    # ========== Responsables Véhicules ==========

    async def set_responsable_vehicule(self, responsable: ResponsableVehiculeData) -> bool:
        """Store responsable véhicule in Valkey."""
        try:
            key = self._key("responsables_vehicules", responsable.email)
            await self.redis.set(key, responsable.model_dump_json())
            await self.redis.sadd(self._key("responsables_vehicules", "index"), responsable.email)
            return True
        except Exception as e:
            logger.error(f"Error setting responsable véhicule {responsable.email} for {self.dt}: {e}")
            return False

    async def get_responsable_vehicule(self, email: str) -> Optional[ResponsableVehiculeData]:
        """Get responsable véhicule by email."""
        data = await self.redis.get(self._key("responsables_vehicules", email))
        if data:
            return ResponsableVehiculeData(**json.loads(data))
        return None

    async def list_responsables_vehicules(self) -> List[str]:
        """List all responsable véhicule emails."""
        members = await self.redis.smembers(self._key("responsables_vehicules", "index"))
        return list(members) if members else []

    async def get_all_responsables_vehicules(self) -> List[ResponsableVehiculeData]:
        """Get all responsables véhicules."""
        emails = await self.list_responsables_vehicules()
        result = []
        for email in emails:
            resp = await self.get_responsable_vehicule(email)
            if resp:
                result.append(resp)
        return result

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

    async def enregistrer_prise(
        self,
        immat: str,
        benevole_nom: str,
        benevole_prenom: str,
        benevole_email: str,
        kilometrage: int,
        niveau_carburant: str,
        etat_general: str,
        observations: str = ""
    ) -> str:
        """
        Enregistrer une prise de véhicule.

        Args:
            immat: Vehicle license plate
            benevole_nom: Volunteer last name
            benevole_prenom: Volunteer first name
            benevole_email: Volunteer email
            kilometrage: Odometer reading
            niveau_carburant: Fuel level
            etat_general: General condition
            observations: Additional observations

        Returns:
            Timestamp of the entry (ISO format)
        """
        timestamp = datetime.now()

        entry = CarnetBordEntry(
            immat=immat,
            dt=self.dt,
            timestamp=timestamp,
            type="Prise",
            benevole_nom=benevole_nom,
            benevole_prenom=benevole_prenom,
            benevole_email=benevole_email,
            kilometrage=kilometrage,
            niveau_carburant=niveau_carburant,
            etat_general=etat_general,
            observations=observations
        )

        await self.add_carnet_entry(entry)

        # Store as derniere_prise for quick lookup
        derniere_prise_key = self._key("carnet", "derniere_prise", immat)
        prise_data = {
            "benevole_nom": benevole_nom,
            "benevole_prenom": benevole_prenom,
            "benevole_email": benevole_email,
            "kilometrage": kilometrage,
            "niveau_carburant": niveau_carburant,
            "etat_general": etat_general,
            "observations": observations,
            "timestamp": timestamp.isoformat()
        }
        await self.redis.set(derniere_prise_key, json.dumps(prise_data))

        return timestamp.isoformat()

    async def enregistrer_retour(
        self,
        immat: str,
        benevole_nom: str,
        benevole_prenom: str,
        benevole_email: str,
        kilometrage: int,
        niveau_carburant: str,
        etat_general: str,
        problemes_signales: str = "",
        observations: str = ""
    ) -> str:
        """
        Enregistrer un retour de véhicule.

        Args:
            immat: Vehicle license plate
            benevole_nom: Volunteer last name
            benevole_prenom: Volunteer first name
            benevole_email: Volunteer email
            kilometrage: Odometer reading
            niveau_carburant: Fuel level
            etat_general: General condition
            problemes_signales: Reported problems
            observations: Additional observations

        Returns:
            Timestamp of the entry (ISO format)
        """
        timestamp = datetime.now()

        entry = CarnetBordEntry(
            immat=immat,
            dt=self.dt,
            timestamp=timestamp,
            type="Retour",
            benevole_nom=benevole_nom,
            benevole_prenom=benevole_prenom,
            benevole_email=benevole_email,
            kilometrage=kilometrage,
            niveau_carburant=niveau_carburant,
            etat_general=etat_general,
            observations=observations,
            problemes_signales=problemes_signales
        )

        await self.add_carnet_entry(entry)

        # Remove derniere_prise since vehicle is returned
        derniere_prise_key = self._key("carnet", "derniere_prise", immat)
        await self.redis.delete(derniere_prise_key)

        return timestamp.isoformat()

    async def get_derniere_prise(self, immat: str) -> Optional[Dict[str, Any]]:
        """
        Récupérer la dernière prise d'un véhicule (véhicule en cours d'utilisation).

        Args:
            immat: Vehicle license plate

        Returns:
            Last prise data or None if vehicle is not currently taken
        """
        derniere_prise_key = self._key("carnet", "derniere_prise", immat)
        data = await self.redis.get(derniere_prise_key)
        return json.loads(data) if data else None

    async def get_historique_carnet(self, immat: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Récupérer l'historique du carnet de bord d'un véhicule.

        Args:
            immat: Vehicle license plate
            limit: Maximum number of entries to return

        Returns:
            List of carnet entries (most recent first)
        """
        entries = await self.get_carnet_entries(immat, limit=limit)
        return [entry.model_dump() for entry in entries]

    # ========== Reservations ==========

    async def create_reservation(
        self,
        reservation_data: ValkeyReservationCreate,
        created_by: str
    ) -> ValkeyReservation:
        """
        Create a new reservation.

        Args:
            reservation_data: Reservation creation data
            created_by: Email of user creating the reservation

        Returns:
            Created reservation with ID and metadata

        Raises:
            ValueError: If reservation overlaps with existing reservation
        """
        # Check for overlaps
        overlaps = await self.check_reservation_overlap(
            vehicule_immat=reservation_data.vehicule_immat,
            debut=reservation_data.debut,
            fin=reservation_data.fin
        )

        if overlaps:
            raise ValueError(
                f"Reservation overlaps with existing reservation(s): {', '.join([r.id for r in overlaps])}"
            )

        # Generate UUID for reservation
        reservation_id = str(uuid.uuid4())
        now = datetime.now()

        # Create full reservation object
        reservation = ValkeyReservation(
            id=reservation_id,
            **reservation_data.model_dump(),
            created_by=created_by,
            created_at=now
        )

        try:
            # Store reservation
            key = self._key("reservations", reservation_id)
            await self.redis.set(key, reservation.model_dump_json())

            # Add to global index
            await self.redis.sadd(self._key("reservations", "index"), reservation_id)

            # Add to date index (for each date in the range)
            current_date = reservation.debut.date()
            end_date = reservation.fin.date()
            while current_date <= end_date:
                date_key = self._key("reservations", "by_date", current_date.isoformat())
                await self.redis.sadd(date_key, reservation_id)
                current_date = date(current_date.year, current_date.month, current_date.day + 1)

            # Add to vehicle index
            vehicle_key = self._key("reservations", "by_vehicle", reservation.vehicule_immat)
            await self.redis.sadd(vehicle_key, reservation_id)

            logger.info(f"Created reservation {reservation_id} for vehicle {reservation.vehicule_immat}")
            return reservation

        except Exception as e:
            logger.error(f"Error creating reservation: {e}")
            raise

    async def get_reservation(self, reservation_id: str) -> Optional[ValkeyReservation]:
        """
        Get a reservation by ID.

        Args:
            reservation_id: Reservation UUID

        Returns:
            Reservation or None if not found
        """
        data = await self.redis.get(self._key("reservations", reservation_id))
        if not data:
            return None
        return ValkeyReservation(**json.loads(data))

    async def list_reservations(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        vehicule_immat: Optional[str] = None
    ) -> List[ValkeyReservation]:
        """
        List reservations with optional filters.

        Args:
            from_date: Filter reservations starting from this date
            to_date: Filter reservations up to this date
            vehicule_immat: Filter by vehicle license plate

        Returns:
            List of reservations matching filters
        """
        reservation_ids: Set[str] = set()

        if vehicule_immat:
            # Get from vehicle index
            vehicle_key = self._key("reservations", "by_vehicle", vehicule_immat)
            ids = await self.redis.smembers(vehicle_key)
            reservation_ids = set(ids) if ids else set()
        elif from_date or to_date:
            # Get from date indexes
            if not from_date:
                from_date = date(2020, 1, 1)  # Default start
            if not to_date:
                to_date = date(2030, 12, 31)  # Default end

            current_date = from_date
            while current_date <= to_date:
                date_key = self._key("reservations", "by_date", current_date.isoformat())
                ids = await self.redis.smembers(date_key)
                if ids:
                    reservation_ids.update(ids)
                # Move to next day
                from datetime import timedelta
                current_date = current_date + timedelta(days=1)
        else:
            # Get all reservations
            ids = await self.redis.smembers(self._key("reservations", "index"))
            reservation_ids = set(ids) if ids else set()

        # Fetch all reservations
        reservations = []
        for res_id in reservation_ids:
            reservation = await self.get_reservation(res_id)
            if reservation:
                # Apply date filters if specified
                if from_date and reservation.fin.date() < from_date:
                    continue
                if to_date and reservation.debut.date() > to_date:
                    continue
                reservations.append(reservation)

        # Sort by start date
        reservations.sort(key=lambda r: r.debut)
        return reservations

    async def update_reservation(
        self,
        reservation_id: str,
        reservation_data: ValkeyReservationCreate
    ) -> Optional[ValkeyReservation]:
        """
        Update an existing reservation.

        Args:
            reservation_id: Reservation UUID
            reservation_data: Updated reservation data

        Returns:
            Updated reservation or None if not found

        Raises:
            ValueError: If update would cause overlap with another reservation
        """
        # Get existing reservation
        existing = await self.get_reservation(reservation_id)
        if not existing:
            return None

        # Check for overlaps (excluding this reservation)
        overlaps = await self.check_reservation_overlap(
            vehicule_immat=reservation_data.vehicule_immat,
            debut=reservation_data.debut,
            fin=reservation_data.fin,
            exclude_id=reservation_id
        )

        if overlaps:
            raise ValueError(
                f"Reservation overlaps with existing reservation(s): {', '.join([r.id for r in overlaps])}"
            )

        try:
            # Update reservation (keep original metadata)
            updated = ValkeyReservation(
                id=reservation_id,
                **reservation_data.model_dump(),
                created_by=existing.created_by,
                created_at=existing.created_at
            )

            # Store updated reservation
            key = self._key("reservations", reservation_id)
            await self.redis.set(key, updated.model_dump_json())

            # Update indexes if vehicle or dates changed
            if existing.vehicule_immat != updated.vehicule_immat:
                # Remove from old vehicle index
                old_vehicle_key = self._key("reservations", "by_vehicle", existing.vehicule_immat)
                await self.redis.srem(old_vehicle_key, reservation_id)

                # Add to new vehicle index
                new_vehicle_key = self._key("reservations", "by_vehicle", updated.vehicule_immat)
                await self.redis.sadd(new_vehicle_key, reservation_id)

            # Update date indexes (remove old, add new)
            # Remove from old dates
            old_current = existing.debut.date()
            old_end = existing.fin.date()
            while old_current <= old_end:
                date_key = self._key("reservations", "by_date", old_current.isoformat())
                await self.redis.srem(date_key, reservation_id)
                from datetime import timedelta
                old_current = old_current + timedelta(days=1)

            # Add to new dates
            new_current = updated.debut.date()
            new_end = updated.fin.date()
            while new_current <= new_end:
                date_key = self._key("reservations", "by_date", new_current.isoformat())
                await self.redis.sadd(date_key, reservation_id)
                from datetime import timedelta
                new_current = new_current + timedelta(days=1)

            logger.info(f"Updated reservation {reservation_id}")
            return updated

        except Exception as e:
            logger.error(f"Error updating reservation {reservation_id}: {e}")
            raise

    async def delete_reservation(self, reservation_id: str) -> bool:
        """
        Delete a reservation.

        Args:
            reservation_id: Reservation UUID

        Returns:
            True if deleted, False if not found
        """
        # Get reservation to clean up indexes
        reservation = await self.get_reservation(reservation_id)
        if not reservation:
            return False

        try:
            # Delete reservation
            key = self._key("reservations", reservation_id)
            await self.redis.delete(key)

            # Remove from global index
            await self.redis.srem(self._key("reservations", "index"), reservation_id)

            # Remove from vehicle index
            vehicle_key = self._key("reservations", "by_vehicle", reservation.vehicule_immat)
            await self.redis.srem(vehicle_key, reservation_id)

            # Remove from date indexes
            current_date = reservation.debut.date()
            end_date = reservation.fin.date()
            from datetime import timedelta
            while current_date <= end_date:
                date_key = self._key("reservations", "by_date", current_date.isoformat())
                await self.redis.srem(date_key, reservation_id)
                current_date = current_date + timedelta(days=1)

            logger.info(f"Deleted reservation {reservation_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting reservation {reservation_id}: {e}")
            return False

    async def check_reservation_overlap(
        self,
        vehicule_immat: str,
        debut: datetime,
        fin: datetime,
        exclude_id: Optional[str] = None
    ) -> List[ValkeyReservation]:
        """
        Check if a reservation would overlap with existing reservations.

        Args:
            vehicule_immat: Vehicle license plate
            debut: Start datetime
            fin: End datetime
            exclude_id: Optional reservation ID to exclude from check (for updates)

        Returns:
            List of overlapping reservations (empty if no overlaps)
        """
        # Get all reservations for this vehicle
        vehicle_reservations = await self.list_reservations(vehicule_immat=vehicule_immat)

        overlaps = []
        for reservation in vehicle_reservations:
            # Skip if this is the reservation being updated
            if exclude_id and reservation.id == exclude_id:
                continue

            # Check for overlap: two periods overlap if one starts before the other ends
            # and ends after the other starts
            if debut < reservation.fin and fin > reservation.debut:
                overlaps.append(reservation)

        return overlaps

