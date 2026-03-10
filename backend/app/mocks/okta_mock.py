"""
Mock Okta OAuth2 service for development and testing.
"""
import secrets
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import jwt


class OktaMock:
    """Mock Okta OAuth2 service that simulates authentication flow."""
    
    def __init__(self):
        """Initialize the mock service."""
        self.mock_secret = "mock-secret-key-for-testing"
        self.mock_users = {
            "thomas.manson@croix-rouge.fr": {
                "sub": "00u1234567890abcdef",
                "email": "thomas.manson@croix-rouge.fr",
                "given_name": "Thomas",
                "family_name": "Manson",
                "name": "Thomas Manson"
            },
            "jean.dupont@croix-rouge.fr": {
                "sub": "00u2234567890abcdef",
                "email": "jean.dupont@croix-rouge.fr",
                "given_name": "Jean",
                "family_name": "Dupont",
                "name": "Jean Dupont"
            },
            "claire.rousseau@croix-rouge.fr": {
                "sub": "00u3234567890abcdef",
                "email": "claire.rousseau@croix-rouge.fr",
                "given_name": "Claire",
                "family_name": "Rousseau",
                "name": "Claire Rousseau"
            },
            "pierre.bernard@croix-rouge.fr": {
                "sub": "00u4234567890abcdef",
                "email": "pierre.bernard@croix-rouge.fr",
                "given_name": "Pierre",
                "family_name": "Bernard",
                "name": "Pierre Bernard"
            }
        }
        self.authorization_codes: Dict[str, str] = {}  # code -> email
    
    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        """
        Generate mock authorization URL.
        
        Args:
            redirect_uri: Callback URL
            state: State parameter for CSRF protection
            
        Returns:
            Mock authorization URL
        """
        # In mock mode, we'll use a simplified URL
        # In real implementation, this would redirect to Okta
        return f"http://localhost:8000/auth/mock-login?redirect_uri={redirect_uri}&state={state}"
    
    def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        
        Args:
            code: Authorization code
            redirect_uri: Callback URL (must match)
            
        Returns:
            Token response with access_token and id_token
        """
        # Get email from stored code
        email = self.authorization_codes.get(code)
        if not email or email not in self.mock_users:
            raise ValueError("Invalid authorization code")
        
        user_data = self.mock_users[email]
        
        # Generate mock tokens
        access_token = self._generate_token(user_data, token_type="access")
        id_token = self._generate_token(user_data, token_type="id")
        
        return {
            "access_token": access_token,
            "id_token": id_token,
            "token_type": "Bearer",
            "expires_in": 3600
        }
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify and decode JWT token.
        
        Args:
            token: JWT token to verify
            
        Returns:
            Decoded token claims
        """
        try:
            payload = jwt.decode(
                token,
                self.mock_secret,
                algorithms=["HS256"],
                options={"verify_exp": True}
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")
    
    def _generate_token(self, user_data: Dict[str, Any], token_type: str = "access") -> str:
        """Generate a mock JWT token."""
        now = datetime.utcnow()
        payload = {
            **user_data,
            "iss": "https://croix-rouge.okta.com/oauth2/default",
            "aud": "mock-client-id",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "token_type": token_type
        }
        
        return jwt.encode(payload, self.mock_secret, algorithm="HS256")
    
    def create_mock_authorization_code(self, email: str) -> str:
        """
        Create a mock authorization code for testing.
        
        Args:
            email: User email
            
        Returns:
            Authorization code
        """
        code = secrets.token_urlsafe(32)
        self.authorization_codes[code] = email
        return code

