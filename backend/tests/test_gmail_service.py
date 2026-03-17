"""Tests for Gmail service."""
import os
import pytest

# Set USE_MOCKS before importing app to avoid Google credentials error
os.environ["USE_MOCKS"] = "true"

from app.services.gmail_service import GmailService


class TestGmailService:
    """Test Gmail service with mocks."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = GmailService()
        self.service.use_mocks = True
    
    @pytest.mark.asyncio
    async def test_send_email_mock(self):
        """Test sending a basic email in mock mode."""
        result = await self.service.send_email(
            dt_id="DT75",
            to="test@croix-rouge.fr",
            subject="Test email",
            body_text="This is a test email.",
        )
        
        assert "id" in result
        assert "threadId" in result
        assert result["labelIds"] == ["SENT"]
        assert "mock-message" in result["id"]
    
    @pytest.mark.asyncio
    async def test_send_email_with_html_mock(self):
        """Test sending an email with HTML body in mock mode."""
        result = await self.service.send_email(
            dt_id="DT75",
            to="test@croix-rouge.fr",
            subject="Test HTML email",
            body_text="Plain text version",
            body_html="<html><body><h1>HTML version</h1></body></html>",
        )
        
        assert "id" in result
        assert "threadId" in result
    
    @pytest.mark.asyncio
    async def test_send_email_with_cc_and_reply_to_mock(self):
        """Test sending an email with CC and Reply-To in mock mode."""
        result = await self.service.send_email(
            dt_id="DT75",
            to="test@croix-rouge.fr",
            subject="Test email with CC",
            body_text="This is a test email.",
            cc=["cc1@croix-rouge.fr", "cc2@croix-rouge.fr"],
            reply_to="manager@croix-rouge.fr",
        )
        
        assert "id" in result
        assert "threadId" in result
    
    @pytest.mark.asyncio
    async def test_send_ct_alert_mock(self):
        """Test sending a CT alert email in mock mode."""
        result = await self.service.send_ct_alert(
            dt_id="DT75",
            vehicle_name="VL Paris 1",
            immatriculation="AA-123-BB",
            ct_expiry_date="2026-05-15",
            recipient_email="assurance@example.com",
            dt_manager_email="thomas.manson@croix-rouge.fr",
        )
        
        assert "id" in result
        assert "threadId" in result
        assert result["labelIds"] == ["SENT"]
    
    @pytest.mark.asyncio
    async def test_send_pollution_alert_mock(self):
        """Test sending a pollution alert email in mock mode."""
        result = await self.service.send_pollution_alert(
            dt_id="DT75",
            vehicle_name="VL Paris 2",
            immatriculation="BB-456-CC",
            pollution_expiry_date="2026-06-20",
            recipient_email="assurance@example.com",
            dt_manager_email="thomas.manson@croix-rouge.fr",
        )
        
        assert "id" in result
        assert "threadId" in result
        assert result["labelIds"] == ["SENT"]
    
    @pytest.mark.asyncio
    async def test_multiple_alerts_mock(self):
        """Test sending multiple alerts in sequence."""
        # Send CT alert
        ct_result = await self.service.send_ct_alert(
            dt_id="DT75",
            vehicle_name="VSAV Paris 1",
            immatriculation="CC-789-DD",
            ct_expiry_date="2026-04-10",
            recipient_email="manager@croix-rouge.fr",
            dt_manager_email="thomas.manson@croix-rouge.fr",
        )
        
        # Send pollution alert
        pollution_result = await self.service.send_pollution_alert(
            dt_id="DT75",
            vehicle_name="VSAV Paris 1",
            immatriculation="CC-789-DD",
            pollution_expiry_date="2026-07-15",
            recipient_email="manager@croix-rouge.fr",
            dt_manager_email="thomas.manson@croix-rouge.fr",
        )
        
        # Both should succeed
        assert "id" in ct_result
        assert "id" in pollution_result
        # IDs should be different
        assert ct_result["id"] != pollution_result["id"]

