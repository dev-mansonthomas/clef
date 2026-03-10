"""Tests for QR code encoding/decoding endpoints."""
import pytest
import os

# Set USE_MOCKS before importing anything
os.environ["USE_MOCKS"] = "true"
os.environ["QR_CODE_SALT"] = "test-salt-for-unit-tests-1234567890"

# Import and configure auth settings BEFORE importing app
from app.auth.config import auth_settings
auth_settings.use_mocks = True

from fastapi.testclient import TestClient
from app.main import app
from app.services.qr_code_service import QrCodeService
from app.auth import routes as auth_routes

client = TestClient(app)


@pytest.fixture
def qr_service():
    """Create QR code service with test SALT."""
    return QrCodeService()


def get_authenticated_client(email: str) -> TestClient:
    """Helper to get an authenticated test client via OAuth flow."""
    okta_mock = auth_routes.okta_mock
    if not okta_mock:
        raise RuntimeError("okta_mock is None - ensure USE_MOCKS=true is set")

    # Create a new client for this test
    test_client = TestClient(app)

    # Go through OAuth flow
    code = okta_mock.create_mock_authorization_code(email)
    response = test_client.get(
        f"/auth/callback?code={code}&state=test-state",
        follow_redirects=False
    )

    # The callback should set a cookie and redirect
    assert response.status_code == 307

    # Extract and set the session cookie on the client
    session_cookie = response.cookies.get(auth_settings.session_cookie_name)
    if session_cookie:
        test_client.cookies.set(auth_settings.session_cookie_name, session_cookie)

    return test_client


class TestQrCodeService:
    """Test QR code service."""
    
    def test_encode_basic(self, qr_service):
        """Test basic encoding."""
        nom_synthetique = "VSAV-PARIS15-01"
        encoded = qr_service.encode(nom_synthetique)
        
        # Should return a non-empty string
        assert encoded
        assert isinstance(encoded, str)
        # Should contain a dot separator (name.signature)
        assert '.' in encoded
    
    def test_encode_empty_raises(self, qr_service):
        """Test encoding empty string raises error."""
        with pytest.raises(ValueError):
            qr_service.encode("")
    
    def test_encode_deterministic(self, qr_service):
        """Test encoding is deterministic."""
        nom_synthetique = "VSAV-PARIS15-01"
        encoded1 = qr_service.encode(nom_synthetique)
        encoded2 = qr_service.encode(nom_synthetique)
        
        assert encoded1 == encoded2
    
    def test_decode_valid(self, qr_service):
        """Test decoding valid encoded ID."""
        nom_synthetique = "VSAV-PARIS15-01"
        encoded = qr_service.encode(nom_synthetique)
        decoded = qr_service.decode(encoded)
        
        assert decoded == nom_synthetique
    
    def test_decode_invalid_format(self, qr_service):
        """Test decoding invalid format returns None."""
        # No dot separator
        assert qr_service.decode("invalid") is None
        # Invalid base64
        assert qr_service.decode("invalid.invalid") is None
    
    def test_decode_tampered(self, qr_service):
        """Test decoding tampered ID returns None."""
        nom_synthetique = "VSAV-PARIS15-01"
        encoded = qr_service.encode(nom_synthetique)
        
        # Tamper with the signature
        parts = encoded.split('.')
        tampered = f"{parts[0]}.AAAA"
        
        assert qr_service.decode(tampered) is None
    
    def test_verify_valid(self, qr_service):
        """Test verification of valid encoded ID."""
        nom_synthetique = "VSAV-PARIS15-01"
        encoded = qr_service.encode(nom_synthetique)
        
        assert qr_service.verify(nom_synthetique, encoded) is True
    
    def test_verify_invalid(self, qr_service):
        """Test verification of invalid encoded ID."""
        nom_synthetique = "VSAV-PARIS15-01"
        wrong_name = "VSAV-PARIS15-02"
        encoded = qr_service.encode(nom_synthetique)
        
        assert qr_service.verify(wrong_name, encoded) is False
    
    def test_get_qr_url(self, qr_service):
        """Test QR URL generation."""
        encoded_id = "test123.sig456"
        url = qr_service.get_qr_url(encoded_id)
        
        assert url.startswith("https://")
        assert "/vehicle/" in url
        assert encoded_id in url
    
    def test_salt_required(self):
        """Test that SALT is required."""
        # Clear SALT
        original = os.environ.get("QR_CODE_SALT")
        os.environ["QR_CODE_SALT"] = ""
        
        with pytest.raises(ValueError, match="QR_CODE_SALT"):
            QrCodeService()
        
        # Restore
        if original:
            os.environ["QR_CODE_SALT"] = original
    
    def test_salt_minimum_length(self):
        """Test that SALT must be at least 16 characters."""
        original = os.environ.get("QR_CODE_SALT")
        os.environ["QR_CODE_SALT"] = "short"
        
        with pytest.raises(ValueError, match="at least 16 characters"):
            QrCodeService()
        
        # Restore
        if original:
            os.environ["QR_CODE_SALT"] = original


class TestQrCodeEndpoints:
    """Test QR code API endpoints."""

    def test_encode_endpoint(self):
        """Test encode endpoint."""
        auth_client = get_authenticated_client("thomas.manson@croix-rouge.fr")

        response = auth_client.post(
            "/api/vehicles/encode",
            json={"nom_synthetique": "VSAV-PARIS15-01"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "encoded_id" in data
        assert "qr_url" in data
        assert '.' in data["encoded_id"]
        assert "/vehicle/" in data["qr_url"]

    def test_decode_endpoint(self):
        """Test decode endpoint (no auth required)."""
        # First encode
        qr_service = QrCodeService()
        nom_synthetique = "VSAV-PARIS15-01"
        encoded_id = qr_service.encode(nom_synthetique)

        # Then decode
        response = client.post(
            "/api/vehicles/decode",
            json={"encoded_id": encoded_id}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["nom_synthetique"] == nom_synthetique

    def test_decode_endpoint_invalid(self):
        """Test decode endpoint with invalid ID."""
        response = client.post(
            "/api/vehicles/decode",
            json={"encoded_id": "invalid.signature"}
        )

        assert response.status_code == 400
        assert "Invalid or tampered" in response.json()["detail"]

    def test_encode_endpoint_empty(self):
        """Test encode endpoint with empty nom_synthetique."""
        auth_client = get_authenticated_client("thomas.manson@croix-rouge.fr")

        response = auth_client.post(
            "/api/vehicles/encode",
            json={"nom_synthetique": ""}
        )

        # Should fail validation
        assert response.status_code == 422

