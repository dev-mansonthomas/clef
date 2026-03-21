"""Valkey service with multi-tenant DT prefixing."""
import logging
import uuid
import secrets
from typing import Optional, List, Dict, Any, Set
from datetime import datetime, date
from redis.asyncio import Redis
from app.models.valkey_models import VehicleData, BenevoleData, ResponsableData, ResponsableVehiculeData, CarnetBordEntry, DTConfiguration
from app.models.reservation import ValkeyReservation, ValkeyReservationCreate
from app.models.repair_models import (
    DossierReparation, Devis, Facture, Fournisseur, HistoriqueEntry,
    FournisseurSnapshot,
    StatutDossier, StatutDevis, ActionHistorique
)

logger = logging.getLogger(__name__)

# Import calendar_service at module level to avoid circular imports
_calendar_service = None

def _get_calendar_service():
    """Lazy import of calendar_service to avoid circular dependencies."""
    global _calendar_service
    if _calendar_service is None:
        from app.services.calendar_service import calendar_service
        _calendar_service = calendar_service
    return _calendar_service


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
        data = await self.redis.json().get(self._key("configuration"))
        if not data:
            return None
        return DTConfiguration(**data)

    async def set_configuration(self, config: DTConfiguration) -> bool:
        """Set DT configuration."""
        try:
            await self.redis.json().set(self._key("configuration"), "$", config.model_dump(mode="json"))
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
        config = await self.redis.json().get(self._key("configuration"))
        if not config:
            config = {}

        # Add API key to config
        if "api_keys" not in config:
            config["api_keys"] = []
        config["api_keys"].append(api_key_data)

        # Save updated config
        await self.redis.json().set(self._key("configuration"), "$", config)

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
        ul_data = await self.redis.json().get(self._key("unite_locale", ul_id))
        if not ul_data:
            raise ValueError(f"UL {ul_id} not found")

        # Add API key to UL data
        if "api_keys" not in ul_data:
            ul_data["api_keys"] = []
        ul_data["api_keys"].append(api_key_data)

        # Save updated UL data
        await self.redis.json().set(self._key("unite_locale", ul_id), "$", ul_data)

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
            ul_data = await self.redis.json().get(self._key("unite_locale", ul_id))
            if not ul_data:
                return False

            api_keys = ul_data.get("api_keys", [])

            for api_key in api_keys:
                if api_key["key"] == key:
                    # Update last_used timestamp
                    api_key["last_used"] = datetime.utcnow().isoformat()
                    await self.redis.json().set(self._key("unite_locale", ul_id), "$", ul_data)
                    return True
            return False
        else:
            # Validate DT-level key
            config = await self.redis.json().get(self._key("configuration"))
            if not config:
                return False

            api_keys = config.get("api_keys", [])

            for api_key in api_keys:
                if api_key["key"] == key:
                    # Update last_used timestamp
                    api_key["last_used"] = datetime.utcnow().isoformat()
                    await self.redis.json().set(self._key("configuration"), "$", config)
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
        config = await self.redis.json().get(self._key("configuration"))
        if not config:
            return []

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
        ul_data = await self.redis.json().get(self._key("unite_locale", ul_id))
        if not ul_data:
            return []

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
        config = await self.redis.json().get(self._key("configuration"))
        if not config:
            return False

        api_keys = config.get("api_keys", [])

        # Filter out the key to delete
        new_keys = [key for key in api_keys if key["id"] != key_id]

        if len(new_keys) == len(api_keys):
            return False  # Key not found

        config["api_keys"] = new_keys
        await self.redis.json().set(self._key("configuration"), "$", config)
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
        ul_data = await self.redis.json().get(self._key("unite_locale", ul_id))
        if not ul_data:
            return False

        api_keys = ul_data.get("api_keys", [])

        # Filter out the key to delete
        new_keys = [key for key in api_keys if key["id"] != key_id]

        if len(new_keys) == len(api_keys):
            return False  # Key not found

        ul_data["api_keys"] = new_keys
        await self.redis.json().set(self._key("unite_locale", ul_id), "$", ul_data)
        return True

    # ========== Vehicles ==========

    async def get_vehicle(self, immat: str) -> Optional[VehicleData]:
        """Get vehicle by license plate."""
        data = await self.redis.json().get(self._key("vehicules", immat))
        if not data:
            return None
        return VehicleData(**data)

    async def set_vehicle(self, vehicle: VehicleData) -> bool:
        """Set vehicle data and add to index."""
        try:
            key = self._key("vehicules", vehicle.immat)
            await self.redis.json().set(key, "$", vehicle.model_dump(mode="json"))
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
        data = await self.redis.json().get(self._key("benevoles", nivol))
        if not data:
            return None
        return BenevoleData(**data)

    async def set_benevole(self, benevole: BenevoleData) -> bool:
        """Set bénévole data and add to indices."""
        try:
            key = self._key("benevoles", benevole.nivol)
            await self.redis.json().set(key, "$", benevole.model_dump(mode="json"))

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

    async def get_benevoles_by_role(self, role: Optional[str] = None) -> List[BenevoleData]:
        """
        Get all bénévoles, optionally filtered by role.

        Args:
            role: Optional role filter ('responsable_ul', 'responsable_dt', or None for all)

        Returns:
            List of BenevoleData objects
        """
        nivols = await self.list_benevoles()
        benevoles = []

        for nivol in nivols:
            benevole = await self.get_benevole(nivol)
            if benevole:
                # Filter by role if specified
                if role is None or benevole.role == role:
                    benevoles.append(benevole)

        return benevoles

    # ========== Responsables ==========

    async def get_responsable(self, email: str) -> Optional[ResponsableData]:
        """Get responsable by email."""
        data = await self.redis.json().get(self._key("responsables", email))
        if not data:
            return None
        return ResponsableData(**data)

    async def set_responsable(self, responsable: ResponsableData) -> bool:
        """Set responsable data and add to index."""
        try:
            key = self._key("responsables", responsable.email)
            await self.redis.json().set(key, "$", responsable.model_dump(mode="json"))

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
            await self.redis.json().set(key, "$", responsable.model_dump(mode="json"))
            await self.redis.sadd(self._key("responsables_vehicules", "index"), responsable.email)
            return True
        except Exception as e:
            logger.error(f"Error setting responsable véhicule {responsable.email} for {self.dt}: {e}")
            return False

    async def get_responsable_vehicule(self, email: str) -> Optional[ResponsableVehiculeData]:
        """Get responsable véhicule by email."""
        data = await self.redis.json().get(self._key("responsables_vehicules", email))
        if data:
            return ResponsableVehiculeData(**data)
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
            await self.redis.json().set(key, "$", entry.model_dump(mode="json"))

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
                data = await self.redis.json().get(key)
                if data:
                    entries.append(CarnetBordEntry(**data))

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
        await self.redis.json().set(derniere_prise_key, "$", prise_data)

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
        data = await self.redis.json().get(derniere_prise_key)
        return data if data else None

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
        Create a new reservation and sync to Google Calendar if configured.

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
            created_at=now,
            google_event_id=None,
            google_event_link=None
        )

        # Try to sync to Google Calendar if configured
        calendar_id = None
        try:
            config_data = await self.redis.json().get(self._key("configuration"))
            calendar_id = config_data.get("calendar_id") if config_data else None
        except Exception:
            # JSON not supported (e.g., in tests with fakeredis) or other error
            pass

        if calendar_id:
            try:
                calendar_service = _get_calendar_service()

                # Get vehicle info for better event summary
                vehicle = await self.get_vehicle(reservation_data.vehicule_immat)
                vehicle_name = vehicle.indicatif if vehicle else reservation_data.vehicule_immat

                event = await calendar_service.create_event(
                    dt_id=self.dt,
                    calendar_id=calendar_id,
                    summary=f"🚗 {vehicle_name} - {reservation_data.chauffeur_nom}",
                    start=reservation_data.debut,
                    end=reservation_data.fin,
                    description=f"Mission: {reservation_data.mission}\nChauffeur: {reservation_data.chauffeur_nom} (NIVOL: {reservation_data.chauffeur_nivol})\n{reservation_data.commentaire or ''}",
                    location=reservation_data.lieu_depart or "",
                    attendees=[created_by] if created_by else None,
                )

                reservation.google_event_id = event.get("id")
                reservation.google_event_link = event.get("htmlLink")
                logger.info(f"Created Google Calendar event {event.get('id')} for reservation {reservation_id}")
            except Exception as e:
                logger.warning(f"Failed to create calendar event for reservation {reservation_id}: {e}")
                # Continue without calendar sync - reservation still valid

        try:
            # Store reservation
            key = self._key("reservations", reservation_id)
            await self.redis.json().set(key, "$", reservation.model_dump(mode="json"))

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
        data = await self.redis.json().get(self._key("reservations", reservation_id))
        if not data:
            return None
        return ValkeyReservation(**data)

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
            # Update reservation (keep original metadata and Google Calendar info)
            updated = ValkeyReservation(
                id=reservation_id,
                **reservation_data.model_dump(),
                created_by=existing.created_by,
                created_at=existing.created_at,
                google_event_id=existing.google_event_id,
                google_event_link=existing.google_event_link
            )

            # Update Google Calendar event if exists
            if existing.google_event_id:
                calendar_id = None
                try:
                    config_data = await self.redis.json().get(self._key("configuration"))
                    calendar_id = config_data.get("calendar_id") if config_data else None
                except Exception:
                    # JSON not supported (e.g., in tests with fakeredis) or other error
                    pass

                if calendar_id:
                    try:
                        calendar_service = _get_calendar_service()

                        # Build updates dict
                        calendar_updates = {}

                        # Update times if changed
                        if reservation_data.debut != existing.debut:
                            calendar_updates["start"] = reservation_data.debut
                        if reservation_data.fin != existing.fin:
                            calendar_updates["end"] = reservation_data.fin

                        # Update summary if vehicle or driver changed
                        if (reservation_data.vehicule_immat != existing.vehicule_immat or
                            reservation_data.chauffeur_nom != existing.chauffeur_nom):
                            vehicle = await self.get_vehicle(reservation_data.vehicule_immat)
                            vehicle_name = vehicle.indicatif if vehicle else reservation_data.vehicule_immat
                            calendar_updates["summary"] = f"🚗 {vehicle_name} - {reservation_data.chauffeur_nom}"

                        # Update description if mission or comment changed
                        if (reservation_data.mission != existing.mission or
                            reservation_data.commentaire != existing.commentaire or
                            reservation_data.chauffeur_nivol != existing.chauffeur_nivol):
                            calendar_updates["description"] = f"Mission: {reservation_data.mission}\nChauffeur: {reservation_data.chauffeur_nom} (NIVOL: {reservation_data.chauffeur_nivol})\n{reservation_data.commentaire or ''}"

                        # Update location if changed
                        if reservation_data.lieu_depart != existing.lieu_depart:
                            calendar_updates["location"] = reservation_data.lieu_depart or ""

                        if calendar_updates:
                            await calendar_service.update_event(
                                dt_id=self.dt,
                                calendar_id=calendar_id,
                                event_id=existing.google_event_id,
                                updates=calendar_updates,
                            )
                            logger.info(f"Updated Google Calendar event {existing.google_event_id} for reservation {reservation_id}")
                    except Exception as e:
                        logger.warning(f"Failed to update calendar event for reservation {reservation_id}: {e}")
                        # Continue without calendar sync - reservation update still valid

            # Store updated reservation
            key = self._key("reservations", reservation_id)
            await self.redis.json().set(key, "$", updated.model_dump(mode="json"))

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
        Delete a reservation and remove from Google Calendar if synced.

        Args:
            reservation_id: Reservation UUID

        Returns:
            True if deleted, False if not found
        """
        # Get reservation to clean up indexes
        reservation = await self.get_reservation(reservation_id)
        if not reservation:
            return False

        # Delete from Google Calendar if exists
        if reservation.google_event_id:
            calendar_id = None
            try:
                config_data = await self.redis.json().get(self._key("configuration"))
                calendar_id = config_data.get("calendar_id") if config_data else None
            except Exception:
                # JSON not supported (e.g., in tests with fakeredis) or other error
                pass

            if calendar_id:
                try:
                    calendar_service = _get_calendar_service()
                    await calendar_service.delete_event(
                        dt_id=self.dt,
                        calendar_id=calendar_id,
                        event_id=reservation.google_event_id,
                    )
                    logger.info(f"Deleted Google Calendar event {reservation.google_event_id} for reservation {reservation_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete calendar event for reservation {reservation_id}: {e}")
                    # Continue with reservation deletion even if calendar delete fails

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

    async def migrate_responsables_to_benevoles(self) -> Dict[str, int]:
        """
        Migrate responsables to benevoles with role field.

        This merges DT:responsables:* into DT:benevoles:* by:
        1. Finding all responsables
        2. For each responsable, check if benevole exists
        3. If benevole exists, update with role from responsable
        4. If benevole doesn't exist, create new benevole with role
        5. Delete responsable entry

        Returns:
            Dict with migration statistics
        """
        stats = {
            "responsables_found": 0,
            "benevoles_updated": 0,
            "benevoles_created": 0,
            "responsables_deleted": 0,
            "errors": 0
        }

        try:
            # Get all responsable emails
            responsable_emails = await self.list_responsables()
            stats["responsables_found"] = len(responsable_emails)

            for email in responsable_emails:
                try:
                    # Get responsable data
                    responsable = await self.get_responsable(email)
                    if not responsable:
                        continue

                    # Determine role based on responsable data
                    # Map "Gestionnaire DT" or similar to "responsable_dt"
                    # Map "Responsable UL" to "responsable_ul"
                    role = None
                    if responsable.role:
                        role_lower = responsable.role.lower()
                        if "gestionnaire" in role_lower or "dt" in role_lower:
                            role = "responsable_dt"
                        elif "ul" in role_lower or "responsable" in role_lower:
                            role = "responsable_ul"

                    # Try to find existing benevole by email
                    # We need to search through all benevoles
                    existing_benevole = None
                    nivols = await self.list_benevoles()
                    for nivol in nivols:
                        benevole = await self.get_benevole(nivol)
                        if benevole and benevole.email and benevole.email.lower() == email.lower():
                            existing_benevole = benevole
                            break

                    if existing_benevole:
                        # Update existing benevole with role
                        updated_benevole = BenevoleData(
                            nivol=existing_benevole.nivol,
                            dt=existing_benevole.dt,
                            ul=existing_benevole.ul or responsable.ul,
                            nom=existing_benevole.nom,
                            prenom=existing_benevole.prenom,
                            email=existing_benevole.email,
                            role=role
                        )
                        await self.set_benevole(updated_benevole)
                        stats["benevoles_updated"] += 1
                    else:
                        # Create new benevole from responsable
                        # Use email as nivol if no nivol available
                        new_benevole = BenevoleData(
                            nivol=email,  # Use email as NIVOL for responsables without NIVOL
                            dt=responsable.dt,
                            ul=responsable.ul,
                            nom=responsable.nom,
                            prenom=responsable.prenom,
                            email=email,
                            role=role
                        )
                        await self.set_benevole(new_benevole)
                        stats["benevoles_created"] += 1

                    # Delete responsable entry
                    await self.delete_responsable(email)
                    stats["responsables_deleted"] += 1

                except Exception as e:
                    logger.error(f"Error migrating responsable {email}: {e}")
                    stats["errors"] += 1
                    continue

            logger.info(f"Migration completed: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Error during migration: {e}")
            stats["errors"] += 1
            return stats

    # ========== Dossiers Réparations ==========

    async def create_dossier_reparation(
        self,
        immat: str,
        description: str,
        cree_par: str,
    ) -> DossierReparation:
        """
        Create a new repair dossier with auto-incremented number.

        Args:
            immat: Vehicle license plate
            description: Description of the repair
            cree_par: Email of the creator

        Returns:
            Created DossierReparation
        """
        # Auto-increment counter
        counter_key = self._key("vehicules", immat, "travaux", "counter")
        counter = await self.redis.incr(counter_key)

        # Format: REP-{YYYY}-{NNN}
        year = datetime.utcnow().year
        numero = f"REP-{year}-{counter:03d}"

        dossier = DossierReparation(
            numero=numero,
            immat=immat,
            dt=self.dt,
            description=description,
            cree_par=cree_par,
            cree_le=datetime.utcnow(),
        )

        # Store dossier
        key = self._key("vehicules", immat, "travaux", numero)
        await self.redis.json().set(key, "$", dossier.model_dump(mode="json"))

        # Add to index
        index_key = self._key("vehicules", immat, "travaux", "index")
        await self.redis.sadd(index_key, numero)

        # Add creation history entry
        await self.add_historique_entry(
            immat=immat,
            numero=numero,
            entry=HistoriqueEntry(
                auteur=cree_par,
                action=ActionHistorique.CREATION,
                details="Dossier créé",
                ref=key,
            ),
        )

        logger.info(f"Created dossier {numero} for vehicle {immat}")
        return dossier

    async def get_dossier_reparation(
        self, immat: str, numero: str
    ) -> Optional[DossierReparation]:
        """Get a repair dossier by number."""
        key = self._key("vehicules", immat, "travaux", numero)
        data = await self.redis.json().get(key)
        if not data:
            return None
        return DossierReparation(**data)

    async def list_dossiers_reparation(self, immat: str) -> List[DossierReparation]:
        """List all repair dossiers for a vehicle, sorted by creation date (newest first)."""
        index_key = self._key("vehicules", immat, "travaux", "index")
        numeros = await self.redis.smembers(index_key)
        if not numeros:
            return []

        dossiers = []
        for numero in numeros:
            dossier = await self.get_dossier_reparation(immat, numero)
            if dossier:
                dossiers.append(dossier)

        # Sort by creation date, newest first
        dossiers.sort(key=lambda d: d.cree_le, reverse=True)
        return dossiers

    async def update_dossier_reparation(
        self, immat: str, numero: str, dossier: DossierReparation
    ) -> bool:
        """Update a repair dossier."""
        try:
            key = self._key("vehicules", immat, "travaux", numero)
            await self.redis.json().set(key, "$", dossier.model_dump(mode="json"))
            return True
        except Exception as e:
            logger.error(f"Error updating dossier {numero}: {e}")
            return False

    # ========== Historique ==========

    async def add_historique_entry(
        self, immat: str, numero: str, entry: HistoriqueEntry
    ) -> bool:
        """Add a history entry for a repair dossier."""
        try:
            hist_key = self._key("vehicules", immat, "travaux", numero, "historique")
            # Get existing history or create empty list
            existing = await self.redis.json().get(hist_key)
            if existing is None:
                existing = []
            existing.append(entry.model_dump(mode="json"))
            await self.redis.json().set(hist_key, "$", existing)
            return True
        except Exception as e:
            logger.error(f"Error adding historique entry for {numero}: {e}")
            return False

    async def get_historique(self, immat: str, numero: str) -> List[HistoriqueEntry]:
        """Get history entries for a repair dossier."""
        hist_key = self._key("vehicules", immat, "travaux", numero, "historique")
        data = await self.redis.json().get(hist_key)
        if not data:
            return []
        return [HistoriqueEntry(**entry) for entry in data]

    # ========== Devis ==========

    async def add_devis(
        self, immat: str, numero_dossier: str, devis_data: dict
    ) -> "Devis":
        """
        Add a devis to a dossier. Auto-increment devis ID within the dossier.

        Args:
            immat: Vehicle license plate
            numero_dossier: Dossier number
            devis_data: Devis data dict (date_devis, fournisseur_id, fournisseur_nom, etc.)

        Returns:
            Created Devis object
        """
        # Auto-increment devis counter for this dossier
        counter_key = self._key("vehicules", immat, "travaux", numero_dossier, "devis", "counter")
        devis_id = str(await self.redis.incr(counter_key))

        # Build fournisseur snapshot
        fournisseur_snapshot = FournisseurSnapshot(
            id=devis_data["fournisseur_id"],
            nom=devis_data["fournisseur_nom"],
        )

        devis = Devis(
            id=devis_id,
            date_devis=devis_data["date_devis"],
            fournisseur=fournisseur_snapshot,
            description=devis_data.get("description_travaux"),
            montant=devis_data["montant"],
            statut=StatutDevis.EN_ATTENTE,
            cree_par=devis_data["cree_par"],
            cree_le=datetime.utcnow(),
        )

        # Store devis at its own key
        devis_key = self._key("vehicules", immat, "travaux", numero_dossier, "devis", devis_id)
        await self.redis.json().set(devis_key, "$", devis.model_dump(mode="json"))

        # Update the dossier's devis list
        dossier = await self.get_dossier_reparation(immat, numero_dossier)
        if dossier:
            dossier.devis.append(devis)
            await self.update_dossier_reparation(immat, numero_dossier, dossier)

        # Add history entry
        await self.add_historique_entry(
            immat=immat,
            numero=numero_dossier,
            entry=HistoriqueEntry(
                auteur=devis_data["cree_par"],
                action=ActionHistorique.DEVIS_AJOUTE,
                details=f"Devis #{devis_id} - {devis_data['fournisseur_nom']} - {devis_data['montant']}€",
                ref=devis_key,
            ),
        )

        logger.info(f"Added devis {devis_id} to dossier {numero_dossier}")
        return devis

    async def get_devis(
        self, immat: str, numero_dossier: str, devis_id: str
    ) -> Optional["Devis"]:
        """Get a specific devis."""
        devis_key = self._key("vehicules", immat, "travaux", numero_dossier, "devis", devis_id)
        data = await self.redis.json().get(devis_key)
        if not data:
            return None
        return Devis(**data)

    async def update_devis(
        self, immat: str, numero_dossier: str, devis_id: str, data: dict
    ) -> Optional["Devis"]:
        """
        Update a devis (e.g. status change).

        Args:
            immat: Vehicle license plate
            numero_dossier: Dossier number
            devis_id: Devis ID
            data: Dict of fields to update (e.g. {"statut": "approuve"})

        Returns:
            Updated Devis or None if not found
        """
        devis = await self.get_devis(immat, numero_dossier, devis_id)
        if not devis:
            return None

        # Apply updates
        for field, value in data.items():
            if hasattr(devis, field):
                setattr(devis, field, value)

        # Save updated devis
        devis_key = self._key("vehicules", immat, "travaux", numero_dossier, "devis", devis_id)
        await self.redis.json().set(devis_key, "$", devis.model_dump(mode="json"))

        # Also update in the dossier's devis list
        dossier = await self.get_dossier_reparation(immat, numero_dossier)
        if dossier:
            for i, d in enumerate(dossier.devis):
                if d.id == devis_id:
                    dossier.devis[i] = devis
                    break
            await self.update_dossier_reparation(immat, numero_dossier, dossier)

        return devis

    # ========== Factures ==========

    async def add_facture(
        self, immat: str, numero_dossier: str, facture_data: dict
    ) -> "Facture":
        """
        Add a facture to a dossier. Auto-increment facture ID.

        Args:
            immat: Vehicle license plate
            numero_dossier: Dossier number
            facture_data: Facture data dict

        Returns:
            Created Facture object
        """
        # Auto-increment facture counter for this dossier
        counter_key = self._key("vehicules", immat, "travaux", numero_dossier, "factures", "counter")
        facture_id = str(await self.redis.incr(counter_key))

        # Build fournisseur snapshot
        fournisseur_snapshot = FournisseurSnapshot(
            id=facture_data["fournisseur_id"],
            nom=facture_data["fournisseur_nom"],
        )

        facture = Facture(
            id=facture_id,
            date_facture=facture_data["date_facture"],
            fournisseur=fournisseur_snapshot,
            classification=facture_data["classification"],
            description=facture_data.get("description_travaux"),
            montant_total=facture_data["montant_total"],
            montant_crf=facture_data["montant_crf"],
            devis_id=facture_data.get("devis_id"),
            cree_par=facture_data["cree_par"],
            cree_le=datetime.utcnow(),
        )

        # Store facture at its own key
        facture_key = self._key("vehicules", immat, "travaux", numero_dossier, "factures", facture_id)
        await self.redis.json().set(facture_key, "$", facture.model_dump(mode="json"))

        # Update the dossier's factures list
        dossier = await self.get_dossier_reparation(immat, numero_dossier)
        if dossier:
            dossier.factures.append(facture)
            await self.update_dossier_reparation(immat, numero_dossier, dossier)

        # Add history entry
        await self.add_historique_entry(
            immat=immat,
            numero=numero_dossier,
            entry=HistoriqueEntry(
                auteur=facture_data["cree_par"],
                action=ActionHistorique.FACTURE_AJOUTEE,
                details=f"Facture #{facture_id} - {facture_data['fournisseur_nom']} - {facture_data['montant_total']}€ TTC",
                ref=facture_key,
            ),
        )

        logger.info(f"Added facture {facture_id} to dossier {numero_dossier}")
        return facture

    async def get_facture(
        self, immat: str, numero_dossier: str, facture_id: str
    ) -> Optional["Facture"]:
        """Get a specific facture."""
        facture_key = self._key("vehicules", immat, "travaux", numero_dossier, "factures", facture_id)
        data = await self.redis.json().get(facture_key)
        if not data:
            return None
        return Facture(**data)

    # ========== Dépenses (Expenses) ==========

    async def get_vehicle_depenses(self, immat: str) -> dict:
        """
        Aggregate all factures across all dossiers for a vehicle,
        grouped by year, sorted by date.

        Returns a dict matching DepensesResponse structure.
        """
        from collections import defaultdict

        dossiers = await self.list_dossiers_reparation(immat)

        # Collect all factures with their dossier numero
        year_data: dict[int, dict] = defaultdict(lambda: {
            "factures": [],
            "dossier_numeros": set(),
            "total_cout": 0.0,
            "total_crf": 0.0,
        })
        total_cout = 0.0
        total_crf = 0.0

        for dossier in dossiers:
            for facture in dossier.factures:
                year = facture.date_facture.year
                entry = year_data[year]
                entry["factures"].append({
                    "date": facture.date_facture.isoformat(),
                    "numero_dossier": dossier.numero,
                    "description": facture.description,
                    "fournisseur_nom": facture.fournisseur.nom,
                    "classification": facture.classification.value if hasattr(facture.classification, 'value') else facture.classification,
                    "montant_total": facture.montant_total,
                    "montant_crf": facture.montant_crf,
                })
                entry["dossier_numeros"].add(dossier.numero)
                entry["total_cout"] += facture.montant_total
                entry["total_crf"] += facture.montant_crf
                total_cout += facture.montant_total
                total_crf += facture.montant_crf

        # Build response sorted by year descending, factures by date
        years = []
        for year in sorted(year_data.keys(), reverse=True):
            data = year_data[year]
            sorted_factures = sorted(data["factures"], key=lambda f: f["date"])
            years.append({
                "year": year,
                "nb_dossiers": len(data["dossier_numeros"]),
                "total_cout": round(data["total_cout"], 2),
                "total_crf": round(data["total_crf"], 2),
                "factures": sorted_factures,
            })

        return {
            "years": years,
            "total_all_years_cout": round(total_cout, 2),
            "total_all_years_crf": round(total_crf, 2),
        }

    # ========== Fournisseurs ==========

    async def set_fournisseur(self, fournisseur: Fournisseur) -> bool:
        """
        Store a supplier. Key depends on niveau (dt or ul).

        DT-level: {DT}:fournisseurs:{id}
        UL-level: {DT}:fournisseurs:UL_{ul_id}:{id}
        """
        try:
            if fournisseur.niveau.value == "ul" and fournisseur.ul_id:
                key = self._key("fournisseurs", f"UL_{fournisseur.ul_id}", fournisseur.id)
                index_key = self._key("fournisseurs", f"UL_{fournisseur.ul_id}", "index")
            else:
                key = self._key("fournisseurs", fournisseur.id)
                index_key = self._key("fournisseurs", "index")

            await self.redis.json().set(key, "$", fournisseur.model_dump(mode="json"))
            await self.redis.sadd(index_key, fournisseur.id)
            return True
        except Exception as e:
            logger.error(f"Error setting fournisseur {fournisseur.id}: {e}")
            return False

    async def get_fournisseur(
        self, fournisseur_id: str, ul_id: Optional[str] = None
    ) -> Optional[Fournisseur]:
        """Get a supplier by ID. Specify ul_id for UL-level suppliers."""
        if ul_id:
            key = self._key("fournisseurs", f"UL_{ul_id}", fournisseur_id)
        else:
            key = self._key("fournisseurs", fournisseur_id)

        data = await self.redis.json().get(key)
        if not data:
            return None
        return Fournisseur(**data)

    async def list_fournisseurs_dt(self) -> List[Fournisseur]:
        """List all DT-level suppliers."""
        index_key = self._key("fournisseurs", "index")
        ids = await self.redis.smembers(index_key)
        if not ids:
            return []

        fournisseurs = []
        for fid in ids:
            f = await self.get_fournisseur(fid)
            if f:
                fournisseurs.append(f)
        return fournisseurs

    async def list_fournisseurs_ul(self, ul_id: str) -> List[Fournisseur]:
        """List all UL-level suppliers for a given UL."""
        index_key = self._key("fournisseurs", f"UL_{ul_id}", "index")
        ids = await self.redis.smembers(index_key)
        if not ids:
            return []

        fournisseurs = []
        for fid in ids:
            f = await self.get_fournisseur(fid, ul_id=ul_id)
            if f:
                fournisseurs.append(f)
        return fournisseurs

    async def list_fournisseurs(self, ul_id: Optional[str] = None) -> List[Fournisseur]:
        """
        List suppliers visible to a user: DT-level + UL-level if ul_id provided.
        """
        dt_fournisseurs = await self.list_fournisseurs_dt()
        if ul_id:
            ul_fournisseurs = await self.list_fournisseurs_ul(ul_id)
            return dt_fournisseurs + ul_fournisseurs
        return dt_fournisseurs
