"""Tests for KMS service."""
import os
import pytest
from unittest.mock import patch, MagicMock

# Set mock mode before import
os.environ["USE_MOCKS"] = "true"

from app.services.kms_service import KMSService


class TestKMSService:
    def setup_method(self):
        self.service = KMSService()
        self.service.use_mocks = True
    
    def test_encrypt_mock(self):
        plaintext = "my-secret-token"
        encrypted = self.service.encrypt(plaintext)
        assert encrypted != plaintext
        assert len(encrypted) > 0
    
    def test_decrypt_mock(self):
        plaintext = "my-secret-token"
        encrypted = self.service.encrypt(plaintext)
        decrypted = self.service.decrypt(encrypted)
        assert decrypted == plaintext
    
    def test_roundtrip_mock(self):
        tokens = [
            "simple-token",
            "token-with-special-chars-!@#$%^&*()",
            "very-long-token-" + "x" * 1000,
            '{"access_token": "abc", "refresh_token": "xyz"}',
        ]
        for token in tokens:
            encrypted = self.service.encrypt(token)
            decrypted = self.service.decrypt(encrypted)
            assert decrypted == token, f"Failed for: {token[:50]}..."

