"""
Service for Gmail operations using DT manager's OAuth tokens.
"""
import base64
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List, Dict, Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.services.dt_token_service import dt_token_service
from app.auth.config import auth_settings

logger = logging.getLogger(__name__)


class GmailService:
    """Service for Gmail operations using DT manager's OAuth tokens."""
    
    def __init__(self):
        self.use_mocks = auth_settings.use_mocks
    
    async def _get_service(self, dt_id: str):
        """Get authenticated Gmail service using DT manager tokens."""
        if self.use_mocks:
            return None
        
        access_token = await dt_token_service.get_access_token(dt_id)
        if not access_token:
            raise ValueError(f"No valid tokens for DT {dt_id}")
        
        credentials = Credentials(token=access_token)
        return build("gmail", "v1", credentials=credentials)
    
    async def send_email(
        self,
        dt_id: str,
        to: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        cc: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send an email using DT manager's Gmail account.
        
        Args:
            dt_id: DT identifier
            to: Recipient email address
            subject: Email subject
            body_text: Plain text body
            body_html: Optional HTML body
            cc: Optional list of CC addresses
            reply_to: Optional Reply-To address
            
        Returns:
            Message resource with id, threadId, etc.
        """
        if self.use_mocks:
            logger.info(f"[MOCK] Sending email to {to}: {subject}")
            return {
                "id": f"mock-message-{subject[:20]}",
                "threadId": "mock-thread-123",
                "labelIds": ["SENT"],
            }
        
        service = await self._get_service(dt_id)
        
        # Get sender email from tokens
        status = await dt_token_service.get_authorization_status(dt_id)
        sender_email = status.get("email", "noreply@croix-rouge.fr")
        
        # Build message
        if body_html:
            message = MIMEMultipart("alternative")
            message.attach(MIMEText(body_text, "plain"))
            message.attach(MIMEText(body_html, "html"))
        else:
            message = MIMEText(body_text)
        
        message["to"] = to
        message["from"] = sender_email
        message["subject"] = subject
        
        if cc:
            message["cc"] = ", ".join(cc)
        
        if reply_to:
            message["reply-to"] = reply_to
        
        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        # Send
        sent = service.users().messages().send(
            userId="me",
            body={"raw": raw_message},
        ).execute()
        
        logger.info(f"Sent email {sent['id']} to {to}")
        return sent
    
    async def send_ct_alert(
        self,
        dt_id: str,
        vehicle_name: str,
        immatriculation: str,
        ct_expiry_date: str,
        recipient_email: str,
        dt_manager_email: str,
    ) -> Dict[str, Any]:
        """
        Send CT expiry alert email.
        """
        subject = f"⚠️ CLEF - Contrôle Technique expirant : {vehicle_name}"
        
        body_text = f"""
Bonjour,

Le contrôle technique du véhicule suivant arrive à expiration :

Véhicule : {vehicle_name}
Immatriculation : {immatriculation}
Date d'expiration CT : {ct_expiry_date}

Merci de prendre les dispositions nécessaires.

Cordialement,
CLEF - Gestion de flotte Croix-Rouge
        """.strip()
        
        body_html = f"""
<html>
<body>
<p>Bonjour,</p>

<p>Le contrôle technique du véhicule suivant arrive à expiration :</p>

<table style="border-collapse: collapse; margin: 20px 0;">
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Véhicule</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{vehicle_name}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Immatriculation</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{immatriculation}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Date d'expiration CT</strong></td><td style="padding: 8px; border: 1px solid #ddd; color: #e74c3c;"><strong>{ct_expiry_date}</strong></td></tr>
</table>

<p>Merci de prendre les dispositions nécessaires.</p>

<p>Cordialement,<br>
<strong>CLEF</strong> - Gestion de flotte Croix-Rouge</p>
</body>
</html>
        """.strip()

        return await self.send_email(
            dt_id=dt_id,
            to=recipient_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            reply_to=dt_manager_email,
        )

    async def send_pollution_alert(
        self,
        dt_id: str,
        vehicle_name: str,
        immatriculation: str,
        pollution_expiry_date: str,
        recipient_email: str,
        dt_manager_email: str,
    ) -> Dict[str, Any]:
        """
        Send pollution control expiry alert email.
        """
        subject = f"⚠️ CLEF - Antipollution expirant : {vehicle_name}"

        body_text = f"""
Bonjour,

Le contrôle antipollution du véhicule suivant arrive à expiration :

Véhicule : {vehicle_name}
Immatriculation : {immatriculation}
Date d'expiration antipollution : {pollution_expiry_date}

Merci de prendre les dispositions nécessaires.

Cordialement,
CLEF - Gestion de flotte Croix-Rouge
        """.strip()

        body_html = f"""
<html>
<body>
<p>Bonjour,</p>

<p>Le contrôle antipollution du véhicule suivant arrive à expiration :</p>

<table style="border-collapse: collapse; margin: 20px 0;">
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Véhicule</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{vehicle_name}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Immatriculation</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{immatriculation}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Date d'expiration antipollution</strong></td><td style="padding: 8px; border: 1px solid #ddd; color: #e74c3c;"><strong>{pollution_expiry_date}</strong></td></tr>
</table>

<p>Merci de prendre les dispositions nécessaires.</p>

<p>Cordialement,<br>
<strong>CLEF</strong> - Gestion de flotte Croix-Rouge</p>
</body>
</html>
        """.strip()

        return await self.send_email(
            dt_id=dt_id,
            to=recipient_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            reply_to=dt_manager_email,
        )


# Global instance
gmail_service = GmailService()

