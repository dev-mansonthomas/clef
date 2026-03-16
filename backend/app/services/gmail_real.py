"""Real Gmail service using Google API client."""
import os
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Dict, List, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.services.gmail import GmailService


class GoogleGmailService(GmailService):
    """Real Gmail service using Google API client."""
    
    SCOPES = ['https://www.googleapis.com/auth/gmail.send']
    
    def __init__(self):
        """Initialize the Gmail service with credentials."""
        self.credentials = self._get_credentials()
        self.service = build('gmail', 'v1', credentials=self.credentials)
        self.service_account_email = os.getenv("SERVICE_ACCOUNT_EMAIL", "")
    
    def _get_credentials(self):
        """Get service account credentials from environment."""
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not credentials_path:
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable not set")
        
        return service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=self.SCOPES
        )
    
    def _create_message(
        self,
        to: str,
        subject: str,
        body: str,
        from_email: Optional[str] = None,
        reply_to: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        html: bool = False
    ) -> Dict[str, str]:
        """
        Create a message for an email.
        
        Args:
            to: Recipient email
            subject: Email subject
            body: Email body
            from_email: Sender email (optional, defaults to service account)
            reply_to: Reply-To email address (optional)
            cc: CC recipients (optional)
            bcc: BCC recipients (optional)
            html: Whether body is HTML
            
        Returns:
            Dictionary with base64 encoded message
        """
        if html:
            message = MIMEMultipart('alternative')
            message.attach(MIMEText(body, 'html'))
        else:
            message = MIMEText(body)
        
        message['to'] = to
        message['from'] = from_email or self.service_account_email
        message['subject'] = subject
        
        if reply_to:
            message['Reply-To'] = reply_to
        
        if cc:
            message['cc'] = ', '.join(cc)
        
        if bcc:
            message['bcc'] = ', '.join(bcc)
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        return {'raw': raw_message}
    
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
        """Send an email via Gmail API."""
        message = self._create_message(
            to=to,
            subject=subject,
            body=body,
            from_email=from_email,
            reply_to=reply_to,
            cc=cc,
            bcc=bcc,
            html=html
        )
        
        result = self.service.users().messages().send(
            userId='me',
            body=message
        ).execute()
        
        return result
    
    def send_alert_email(
        self,
        to: str,
        vehicle_name: str,
        alert_type: str,
        expiry_date: str,
        from_email: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a vehicle alert email (CT or pollution expiry)."""
        subject = f"[CLEF] Alerte {alert_type} - {vehicle_name}"
        
        # HTML email template
        body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #e30613; color: white; padding: 20px; text-align: center; }}
        .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
        .alert-box {{ background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 15px 0; }}
        .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>CLEF - Gestion des Véhicules</h2>
        </div>
        <div class="content">
            <p>Bonjour,</p>
            <div class="alert-box">
                <strong>⚠️ Alerte : {alert_type}</strong><br>
                <strong>Véhicule :</strong> {vehicle_name}<br>
                <strong>Date d'expiration :</strong> {expiry_date}
            </div>
            <p>Le véhicule mentionné ci-dessus nécessite votre attention. Merci de prendre les dispositions nécessaires pour renouveler le {alert_type.lower()}.</p>
        </div>
        <div class="footer">
            <p>Cet email a été envoyé automatiquement par le système CLEF.<br>
            Croix-Rouge Française</p>
        </div>
    </div>
</body>
</html>
"""
        
        return self.send_email(
            to=to,
            subject=subject,
            body=body,
            from_email=from_email,
            reply_to=reply_to,
            html=True
        )

