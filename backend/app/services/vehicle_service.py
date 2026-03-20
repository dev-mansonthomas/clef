"""Vehicle service with business logic."""
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from app.models.vehicle import Vehicle, StatusInfo, StatusColor, DisponibiliteStatus, VehicleBase
from app.auth.models import User



class VehicleService:
    """Service for vehicle-related business logic."""
    
    ALERT_THRESHOLD_DAYS = 60  # 2 months
    
    @staticmethod
    def calculate_status(expiry_date_str: Optional[str]) -> StatusInfo:
        """
        Calculate status based on expiry date.
        
        Rules:
        - Red: Expired (date in the past)
        - Orange: Expires in less than 2 months (60 days)
        - Green: OK (more than 2 months until expiry)
        
        Args:
            expiry_date_str: Date string in YYYY-MM-DD format
            
        Returns:
            StatusInfo with color and days until expiry
        """
        if not expiry_date_str:
            return StatusInfo(
                value="N/A",
                color=StatusColor.RED,
                days_until_expiry=None
            )
        
        try:
            expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d").date()
            today = date.today()
            days_until_expiry = (expiry_date - today).days
            
            if days_until_expiry < 0:
                # Expired
                color = StatusColor.RED
            elif days_until_expiry < VehicleService.ALERT_THRESHOLD_DAYS:
                # Expiring soon (< 2 months)
                color = StatusColor.ORANGE
            else:
                # OK
                color = StatusColor.GREEN
            
            return StatusInfo(
                value=expiry_date_str,
                color=color,
                days_until_expiry=days_until_expiry
            )
        except ValueError:
            # Invalid date format
            return StatusInfo(
                value=expiry_date_str,
                color=StatusColor.RED,
                days_until_expiry=None
            )
    
    @staticmethod
    def calculate_disponibilite_status(
        operationnel_mecanique: DisponibiliteStatus
    ) -> StatusInfo:
        """
        Calculate availability status.
        
        Args:
            operationnel_mecanique: Availability status
            
        Returns:
            StatusInfo with color
        """
        if operationnel_mecanique == DisponibiliteStatus.DISPO:
            color = StatusColor.GREEN
        else:
            color = StatusColor.RED
        
        return StatusInfo(
            value=operationnel_mecanique.value,
            color=color,
            days_until_expiry=None
        )
    
    @staticmethod
    def enrich_vehicle(vehicle_data: Dict[str, Any]) -> Vehicle:
        """
        Enrich vehicle data with computed status fields.

        Args:
            vehicle_data: Raw vehicle data from sheets

        Returns:
            Vehicle model with status fields
        """
        # Calculate statuses
        status_ct = VehicleService.calculate_status(
            vehicle_data.get("prochain_controle_technique")
        )
        status_pollution = VehicleService.calculate_status(
            vehicle_data.get("prochain_controle_pollution")
        )

        # Normalize disponibilite value before creating enum
        raw_dispo = vehicle_data.get("operationnel_mecanique", "Indispo")
        dispo_status = DisponibiliteStatus.normalize(raw_dispo)
        status_disponibilite = VehicleService.calculate_disponibilite_status(dispo_status)

        # Update vehicle_data with normalized value
        vehicle_data["operationnel_mecanique"] = dispo_status

        # Create vehicle model
        return Vehicle(
            **vehicle_data,
            status_ct=status_ct,
            status_pollution=status_pollution,
            status_disponibilite=status_disponibilite
        )
    
    @staticmethod
    def filter_by_user_access(
        vehicles: List[Dict[str, Any]],
        user: User
    ) -> List[Dict[str, Any]]:
        """
        Filter vehicles based on user's access rights.

        - Gestionnaire DT: sees all vehicles
        - Responsable UL: sees only vehicles from their UL
        - Others: see only vehicles from their UL

        Args:
            vehicles: List of raw vehicle data
            user: Current user

        Returns:
            Filtered list of vehicles
        """
        if user.role == "Gestionnaire DT":
            # DT manager sees all vehicles
            return vehicles

        # Filter by UL
        user_ul = user.ul or user.perimetre
        if not user_ul:
            return []

        return [
            v for v in vehicles
            if v.get("dt_ul") == user_ul
        ]

