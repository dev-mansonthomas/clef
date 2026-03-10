"""Gmail service interface and factory."""
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class GmailService(ABC):
    """Abstract base class for Gmail service."""
    
    @abstractmethod
    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        from_email: Optional[str] = None,
        reply_to: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        html: bool = False
    ) -> Dict[str, Any]:
        """
        Send an email.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body
            from_email: Sender email (optional)
            reply_to: Reply-To email address (optional)
            cc: CC recipients (optional)
            bcc: BCC recipients (optional)
            html: Whether body is HTML
            
        Returns:
            Message metadata
        """
        pass
    
    @abstractmethod
    def send_alert_email(
        self,
        to: str,
        vehicle_name: str,
        alert_type: str,
        expiry_date: str,
        from_email: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a vehicle alert email (CT or pollution expiry).
        
        Args:
            to: Recipient email
            vehicle_name: Vehicle name
            alert_type: Type of alert (CT or Pollution)
            expiry_date: Expiry date
            from_email: Sender email (optional)
            reply_to: Reply-To email address (optional)
            
        Returns:
            Message metadata
        """
        pass


def get_gmail_service() -> GmailService:
    """
    Factory function to get the appropriate Gmail service implementation.
    
    Returns:
        GmailService implementation (mock or real based on USE_MOCKS env var)
    """
    use_mocks = os.getenv("USE_MOCKS", "false").lower() == "true"
    
    if use_mocks:
        from app.mocks.google_gmail_mock import GoogleGmailMock
        return GoogleGmailMock()
    else:
        from app.services.gmail_real import GoogleGmailService
        return GoogleGmailService()

