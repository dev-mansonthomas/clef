"""QR Code service for secure vehicle ID encoding/decoding."""
import os
import hashlib
import base64
import hmac
from typing import Optional


class QrCodeService:
    """Service for encoding and decoding vehicle IDs with SALT using HMAC."""

    def __init__(self):
        """Initialize QR code service with SALT from environment."""
        self.salt = os.getenv("QR_CODE_SALT", "")
        if not self.salt or len(self.salt) < 16:
            raise ValueError(
                "QR_CODE_SALT must be set and at least 16 characters long"
            )

    def encode(self, nom_synthetique: str) -> str:
        """
        Encode a vehicle nom_synthetique with HMAC signature.

        The encoding process:
        1. Base64 encode the nom_synthetique
        2. Generate HMAC-SHA256 signature using SALT
        3. Combine: base64(nom_synthetique) + "." + base64(signature[:8])
        4. Make URL-safe

        This allows decoding while preventing tampering.

        Args:
            nom_synthetique: Vehicle synthetic name

        Returns:
            URL-safe encoded ID with signature

        Raises:
            ValueError: If nom_synthetique is empty
        """
        if not nom_synthetique:
            raise ValueError("nom_synthetique cannot be empty")

        # Base64 encode the nom_synthetique
        encoded_name = base64.urlsafe_b64encode(
            nom_synthetique.encode('utf-8')
        ).decode('utf-8').rstrip('=')

        # Generate HMAC signature
        signature = hmac.new(
            self.salt.encode('utf-8'),
            nom_synthetique.encode('utf-8'),
            hashlib.sha256
        ).digest()

        # Take first 8 bytes of signature for shorter QR codes
        short_sig = signature[:8]
        encoded_sig = base64.urlsafe_b64encode(short_sig).decode('utf-8').rstrip('=')

        # Combine: encoded_name.signature
        return f"{encoded_name}.{encoded_sig}"

    def decode(self, encoded_id: str) -> Optional[str]:
        """
        Decode an encoded vehicle ID back to nom_synthetique.

        Validates the HMAC signature to prevent tampering.

        Args:
            encoded_id: Encoded vehicle ID with signature

        Returns:
            Vehicle synthetic name if signature is valid, None otherwise
        """
        try:
            # Split into name and signature
            if '.' not in encoded_id:
                return None

            encoded_name, encoded_sig = encoded_id.split('.', 1)

            # Add padding back for base64 decoding
            encoded_name += '=' * (4 - len(encoded_name) % 4)

            # Decode the nom_synthetique
            nom_synthetique = base64.urlsafe_b64decode(
                encoded_name.encode('utf-8')
            ).decode('utf-8')

            # Verify signature
            if not self.verify(nom_synthetique, encoded_id):
                return None

            return nom_synthetique

        except Exception:
            return None

    def verify(self, nom_synthetique: str, encoded_id: str) -> bool:
        """
        Verify that an encoded_id matches a nom_synthetique.

        Args:
            nom_synthetique: Vehicle synthetic name to verify
            encoded_id: Encoded ID to check against

        Returns:
            True if the encoded_id matches the nom_synthetique
        """
        try:
            expected_encoded = self.encode(nom_synthetique)
            return expected_encoded == encoded_id
        except Exception:
            return False

    def get_qr_url(self, encoded_id: str) -> str:
        """
        Generate the full QR code URL for a vehicle.

        Args:
            encoded_id: Encoded vehicle ID

        Returns:
            Full URL to encode in QR code
        """
        domain = os.getenv("DOMAIN", "clef.example.com")
        return f"https://{domain}/vehicle/{encoded_id}"

