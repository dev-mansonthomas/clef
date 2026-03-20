"""
KMS Service for encrypting/decrypting sensitive data (OAuth tokens).
"""
import base64
import os
from typing import Optional
from google.cloud import kms


class KMSService:
    def __init__(self):
        self.project_id = os.getenv("GCP_PROJECT_ID") or os.getenv("GCP_PROJECT")
        self.location = os.getenv("GCP_REGION", "europe-west9")
        self.environment = os.getenv("ENVIRONMENT", "local")
        self.keyring_name = f"clef-{self.environment}-keyring"
        self.key_name = "oauth-tokens-key"
        
        # Client KMS (None en mode mock)
        self._client: Optional[kms.KeyManagementServiceClient] = None
        self.use_mocks = os.getenv("USE_MOCKS", "false").lower() == "true"
    
    @property
    def client(self) -> kms.KeyManagementServiceClient:
        if self._client is None:
            self._client = kms.KeyManagementServiceClient()
        return self._client
    
    @property
    def key_path(self) -> str:
        return self.client.crypto_key_path(
            self.project_id,
            self.location,
            self.keyring_name,
            self.key_name
        )
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext and return base64-encoded ciphertext."""
        if self.use_mocks:
            # Mock: just base64 encode (NOT SECURE - dev only)
            return base64.b64encode(f"MOCK:{plaintext}".encode()).decode()
        
        plaintext_bytes = plaintext.encode("utf-8")
        response = self.client.encrypt(
            request={"name": self.key_path, "plaintext": plaintext_bytes}
        )
        return base64.b64encode(response.ciphertext).decode()
    
    def decrypt(self, ciphertext_b64: str) -> str:
        """Decrypt base64-encoded ciphertext and return plaintext."""
        if self.use_mocks:
            # Mock: just decode and strip prefix
            decoded = base64.b64decode(ciphertext_b64).decode()
            if decoded.startswith("MOCK:"):
                return decoded[5:]
            return decoded
        
        ciphertext = base64.b64decode(ciphertext_b64)
        response = self.client.decrypt(
            request={"name": self.key_path, "ciphertext": ciphertext}
        )
        return response.plaintext.decode("utf-8")


# Singleton instance
kms_service = KMSService()

