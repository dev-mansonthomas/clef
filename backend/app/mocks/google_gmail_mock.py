"""Mock implementation of Google Gmail API service."""
from typing import Any, Dict, List, Optional
from datetime import datetime


class GoogleGmailMock:
    """Mock Gmail service for sending emails."""
    
    def __init__(self):
        """Initialize the mock service."""
        self._sent_messages: List[Dict[str, Any]] = []
    
    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        from_email: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        html: bool = False
    ) -> Dict[str, Any]:
        """
        Mock email sending.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body
            from_email: Sender email (optional)
            cc: CC recipients (optional)
            bcc: BCC recipients (optional)
            html: Whether body is HTML
            
        Returns:
            Mock message metadata
        """
        message_id = f"mock-message-{datetime.now().timestamp()}"
        message = {
            "id": message_id,
            "threadId": f"mock-thread-{datetime.now().timestamp()}",
            "to": to,
            "from": from_email or "noreply@croix-rouge.fr",
            "subject": subject,
            "body": body,
            "cc": cc or [],
            "bcc": bcc or [],
            "html": html,
            "timestamp": datetime.now().isoformat(),
            "labelIds": ["SENT"]
        }
        
        self._sent_messages.append(message)
        return message
    
    def get_sent_messages(self) -> List[Dict[str, Any]]:
        """
        Get all sent messages (for testing).
        
        Returns:
            List of sent message metadata
        """
        return self._sent_messages.copy()
    
    def clear_sent_messages(self) -> None:
        """Clear all sent messages (for testing)."""
        self._sent_messages.clear()
    
    def send_alert_email(
        self,
        to: str,
        vehicle_name: str,
        alert_type: str,
        expiry_date: str,
        from_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a vehicle alert email (CT or pollution expiry).
        
        Args:
            to: Recipient email
            vehicle_name: Vehicle name
            alert_type: Type of alert (CT or Pollution)
            expiry_date: Expiry date
            from_email: Sender email (optional)
            
        Returns:
            Mock message metadata
        """
        subject = f"[CLEF] Alerte {alert_type} - {vehicle_name}"
        body = f"""
Bonjour,

Le véhicule {vehicle_name} nécessite votre attention :

Type d'alerte : {alert_type}
Date d'expiration : {expiry_date}

Merci de prendre les dispositions nécessaires.

Cordialement,
Système CLEF - Gestion des Véhicules
"""
        
        return self.send_email(
            to=to,
            subject=subject,
            body=body,
            from_email=from_email
        )

