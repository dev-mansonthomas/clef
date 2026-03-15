"""Statistics service for dashboard."""
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from app.services.valkey_service import ValkeyService
from app.models.valkey_models import VehicleData
from app.models.reservation import ValkeyReservation

logger = logging.getLogger(__name__)


class StatsService:
    """Service for calculating vehicle statistics."""
    
    ALERT_THRESHOLD_DAYS = 60  # 2 months
    
    @staticmethod
    async def get_dashboard_stats(valkey_service: ValkeyService) -> Dict[str, Any]:
        """
        Calculate dashboard statistics for vehicles.
        
        Args:
            valkey_service: Valkey service instance
            
        Returns:
            Dictionary with statistics
        """
        # Get all vehicles
        vehicle_immats = await valkey_service.list_vehicles()
        vehicles: List[VehicleData] = []
        for immat in vehicle_immats:
            vehicle_data = await valkey_service.get_vehicle(immat)
            if vehicle_data:
                vehicles.append(vehicle_data)
        
        total_vehicules = len(vehicles)
        
        # Get current reservations to determine availability
        today = datetime.now().date()
        now = datetime.now()
        
        # Get all reservations
        all_reservation_ids = await valkey_service.redis.smembers(
            valkey_service._key("reservations", "index")
        )
        
        # Check which vehicles are currently reserved
        reserved_immats = set()
        for res_id in all_reservation_ids:
            reservation_data = await valkey_service.get_reservation(res_id)
            if reservation_data:
                # Check if reservation is active now
                if reservation_data.debut <= now <= reservation_data.fin:
                    reserved_immats.add(reservation_data.vehicule_immat)
        
        # Calculate availability
        disponibles = 0
        indisponibles = 0
        for vehicle in vehicles:
            # Vehicle is unavailable if mechanically unavailable OR currently reserved
            if vehicle.operationnel_mecanique != "Dispo" or vehicle.immat in reserved_immats:
                indisponibles += 1
            else:
                disponibles += 1
        
        # Calculate CT statistics
        ct_stats = StatsService._calculate_date_stats(
            vehicles, 
            lambda v: v.prochain_controle_technique
        )
        
        # Calculate pollution statistics
        pollution_stats = StatsService._calculate_date_stats(
            vehicles,
            lambda v: v.prochain_controle_pollution
        )
        
        # Generate alerts list
        alertes = StatsService._generate_alerts(vehicles)
        
        return {
            "total_vehicules": total_vehicules,
            "disponibles": disponibles,
            "indisponibles": indisponibles,
            "ct": ct_stats,
            "pollution": pollution_stats,
            "alertes": alertes
        }
    
    @staticmethod
    def _calculate_date_stats(
        vehicles: List[VehicleData],
        date_getter: callable
    ) -> Dict[str, int]:
        """
        Calculate statistics for a date field (CT or pollution).
        
        Args:
            vehicles: List of vehicles
            date_getter: Function to extract date from vehicle
            
        Returns:
            Dictionary with en_retard, dans_2_mois, ok counts
        """
        today = date.today()
        threshold_date = today + timedelta(days=StatsService.ALERT_THRESHOLD_DAYS)
        
        en_retard = 0
        dans_2_mois = 0
        ok = 0
        
        for vehicle in vehicles:
            date_str = date_getter(vehicle)
            if not date_str:
                # No date = consider as expired
                en_retard += 1
                continue
            
            try:
                check_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                
                if check_date < today:
                    en_retard += 1
                elif check_date <= threshold_date:
                    dans_2_mois += 1
                else:
                    ok += 1
            except ValueError:
                # Invalid date format = consider as expired
                en_retard += 1
        
        return {
            "en_retard": en_retard,
            "dans_2_mois": dans_2_mois,
            "ok": ok
        }
    
    @staticmethod
    def _generate_alerts(vehicles: List[VehicleData]) -> List[Dict[str, Any]]:
        """
        Generate list of vehicles requiring attention.
        
        Args:
            vehicles: List of vehicles
            
        Returns:
            List of alert dictionaries
        """
        today = date.today()
        threshold_date = today + timedelta(days=StatsService.ALERT_THRESHOLD_DAYS)
        
        alertes = []
        
        for vehicle in vehicles:
            # Check CT
            if vehicle.prochain_controle_technique:
                try:
                    ct_date = datetime.strptime(vehicle.prochain_controle_technique, "%Y-%m-%d").date()
                    days = (ct_date - today).days
                    
                    if days < 0:
                        alertes.append({
                            "immatriculation": vehicle.immat,
                            "marque": vehicle.marque,
                            "modele": vehicle.modele,
                            "type": "ct_expire",
                            "date": vehicle.prochain_controle_technique,
                            "jours": days
                        })
                    elif ct_date <= threshold_date:
                        alertes.append({
                            "immatriculation": vehicle.immat,
                            "marque": vehicle.marque,
                            "modele": vehicle.modele,
                            "type": "ct_bientot",
                            "date": vehicle.prochain_controle_technique,
                            "jours": days
                        })
                except ValueError:
                    pass
            
            # Check pollution
            if vehicle.prochain_controle_pollution:
                try:
                    pollution_date = datetime.strptime(vehicle.prochain_controle_pollution, "%Y-%m-%d").date()
                    days = (pollution_date - today).days
                    
                    if days < 0:
                        alertes.append({
                            "immatriculation": vehicle.immat,
                            "marque": vehicle.marque,
                            "modele": vehicle.modele,
                            "type": "pollution_expire",
                            "date": vehicle.prochain_controle_pollution,
                            "jours": days
                        })
                    elif pollution_date <= threshold_date:
                        alertes.append({
                            "immatriculation": vehicle.immat,
                            "marque": vehicle.marque,
                            "modele": vehicle.modele,
                            "type": "pollution_bientot",
                            "date": vehicle.prochain_controle_pollution,
                            "jours": days
                        })
                except ValueError:
                    pass
        
        # Sort by urgency (most urgent first)
        alertes.sort(key=lambda x: x["jours"])
        
        return alertes

