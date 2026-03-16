"""Alert service for checking vehicle CT and pollution expiry dates."""
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from app.services.gmail import get_gmail_service
from app.services.sheets import get_sheets_service
from app.services.config_service import ConfigService

logger = logging.getLogger(__name__)


class AlertService:
    """Service for checking and sending vehicle alerts."""
    
    def __init__(self, config_service: ConfigService):
        """
        Initialize the alert service.
        
        Args:
            config_service: Configuration service instance
        """
        self.config_service = config_service
        self.gmail_service = get_gmail_service()
        self.sheets_service = get_sheets_service()
        self.alert_delay_days = int(os.getenv("ALERT_DELAY_DAYS", "60"))
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse a date string in various formats.
        
        Args:
            date_str: Date string to parse
            
        Returns:
            Datetime object or None if parsing fails
        """
        if not date_str or date_str.strip() == "":
            return None
        
        # Try common date formats
        formats = [
            "%d/%m/%Y",  # 15/03/2026
            "%Y-%m-%d",  # 2026-03-15
            "%d-%m-%Y",  # 15-03-2026
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        
        logger.warning(f"Could not parse date: {date_str}")
        return None
    
    def _check_expiry(self, expiry_date: Optional[datetime]) -> bool:
        """
        Check if a date is expiring within the alert delay.
        
        Args:
            expiry_date: Expiry date to check
            
        Returns:
            True if expiring within alert delay, False otherwise
        """
        if not expiry_date:
            return False
        
        today = datetime.now()
        alert_threshold = today + timedelta(days=self.alert_delay_days)
        
        # Alert if expiry is in the past or within the alert delay
        return expiry_date <= alert_threshold
    
    async def check_and_send_alerts(self) -> Dict[str, Any]:
        """
        Check all vehicles and send alerts for expiring CT/pollution.
        
        Returns:
            Dictionary with alert statistics
        """
        logger.info("Starting vehicle alert check")
        
        # Get configuration
        config = await self.config_service.get_config()
        recipient_email = config.get("email_destinataire_alertes")
        dt_email = config.get("email_gestionnaire_dt")
        
        if not recipient_email:
            logger.error("No recipient email configured for alerts")
            return {
                "success": False,
                "error": "No recipient email configured",
                "alerts_sent": 0
            }
        
        # Get all vehicles
        vehicles = self.sheets_service.get_vehicles()
        logger.info(f"Checking {len(vehicles)} vehicles")
        
        alerts_sent = 0
        ct_alerts = []
        pollution_alerts = []
        
        for vehicle in vehicles:
            vehicle_name = vehicle.get("Nom Synthétique") or vehicle.get("Immat", "Unknown")
            
            # Check CT expiry (column F: "Prochain Controle Technique")
            ct_date_str = vehicle.get("Prochain Controle Technique", "")
            ct_date = self._parse_date(ct_date_str)
            
            if self._check_expiry(ct_date):
                ct_alerts.append({
                    "vehicle": vehicle_name,
                    "immat": vehicle.get("Immat", ""),
                    "expiry_date": ct_date_str,
                    "type": "Contrôle Technique"
                })
            
            # Check pollution expiry (column G: "Prochain Controle Pollution")
            pollution_date_str = vehicle.get("Prochain Controle Pollution", "")
            pollution_date = self._parse_date(pollution_date_str)
            
            if self._check_expiry(pollution_date):
                pollution_alerts.append({
                    "vehicle": vehicle_name,
                    "immat": vehicle.get("Immat", ""),
                    "expiry_date": pollution_date_str,
                    "type": "Contrôle Antipollution"
                })
        
        # Send consolidated alert email if there are any alerts
        total_alerts = len(ct_alerts) + len(pollution_alerts)
        
        if total_alerts > 0:
            try:
                self._send_consolidated_alert(
                    recipient_email=recipient_email,
                    dt_email=dt_email,
                    ct_alerts=ct_alerts,
                    pollution_alerts=pollution_alerts
                )
                alerts_sent = 1
                logger.info(f"Sent consolidated alert email with {total_alerts} vehicle alerts")
            except Exception as e:
                logger.error(f"Failed to send alert email: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "alerts_sent": 0,
                    "ct_alerts": len(ct_alerts),
                    "pollution_alerts": len(pollution_alerts)
                }
        else:
            logger.info("No vehicles requiring alerts")
        
        return {
            "success": True,
            "alerts_sent": alerts_sent,
            "ct_alerts": len(ct_alerts),
            "pollution_alerts": len(pollution_alerts),
            "total_vehicles_checked": len(vehicles)
        }

    def _send_consolidated_alert(
        self,
        recipient_email: str,
        dt_email: Optional[str],
        ct_alerts: List[Dict[str, str]],
        pollution_alerts: List[Dict[str, str]]
    ) -> None:
        """
        Send a consolidated alert email with all expiring vehicles.

        Args:
            recipient_email: Email recipient
            dt_email: DT manager email for Reply-To
            ct_alerts: List of CT alerts
            pollution_alerts: List of pollution alerts
        """
        subject = f"[CLEF] Alertes Véhicules - {len(ct_alerts)} CT, {len(pollution_alerts)} Antipollution"

        # Build HTML table for CT alerts
        ct_rows = ""
        for alert in ct_alerts:
            ct_rows += f"""
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;">{alert['vehicle']}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{alert['immat']}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{alert['expiry_date']}</td>
                </tr>
            """

        # Build HTML table for pollution alerts
        pollution_rows = ""
        for alert in pollution_alerts:
            pollution_rows += f"""
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;">{alert['vehicle']}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{alert['immat']}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{alert['expiry_date']}</td>
                </tr>
            """

        # HTML email template
        body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #e30613; color: white; padding: 20px; text-align: center; }}
        .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
        .alert-section {{ margin: 20px 0; }}
        .alert-section h3 {{ color: #e30613; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; background-color: white; }}
        th {{ background-color: #e30613; color: white; padding: 10px; text-align: left; }}
        td {{ padding: 8px; border: 1px solid #ddd; }}
        .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>CLEF - Alertes Véhicules</h2>
        </div>
        <div class="content">
            <p>Bonjour,</p>
            <p>Les véhicules suivants nécessitent votre attention pour renouvellement de contrôle technique ou antipollution (expiration dans moins de {self.alert_delay_days} jours) :</p>

            {f'''
            <div class="alert-section">
                <h3>⚠️ Contrôles Techniques ({len(ct_alerts)})</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Véhicule</th>
                            <th>Immatriculation</th>
                            <th>Date d'expiration</th>
                        </tr>
                    </thead>
                    <tbody>
                        {ct_rows}
                    </tbody>
                </table>
            </div>
            ''' if ct_alerts else ''}

            {f'''
            <div class="alert-section">
                <h3>⚠️ Contrôles Antipollution ({len(pollution_alerts)})</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Véhicule</th>
                            <th>Immatriculation</th>
                            <th>Date d'expiration</th>
                        </tr>
                    </thead>
                    <tbody>
                        {pollution_rows}
                    </tbody>
                </table>
            </div>
            ''' if pollution_alerts else ''}

            <p>Merci de prendre les dispositions nécessaires pour effectuer ces contrôles.</p>
        </div>
        <div class="footer">
            <p>Cet email a été envoyé automatiquement par le système CLEF.<br>
            Croix-Rouge Française</p>
        </div>
    </div>
</body>
</html>
"""

        self.gmail_service.send_email(
            to=recipient_email,
            subject=subject,
            body=body,
            reply_to=dt_email,
            html=True
        )

