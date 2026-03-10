"""
Tests for authentication module.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.auth.config import auth_settings


# Ensure we're using mocks for tests
auth_settings.use_mocks = True

client = TestClient(app)

# Import okta_mock from routes to use the same instance
from app.auth import routes
okta_mock = routes.okta_mock


class TestAuthEndpoints:
    """Test authentication endpoints."""
    
    def test_login_endpoint(self):
        """Test /auth/login returns authorization URL."""
        response = client.get("/auth/login")
        assert response.status_code == 200
        data = response.json()
        assert "authorization_url" in data
        assert "mock-login" in data["authorization_url"]
    
    def test_me_endpoint_without_auth(self):
        """Test /auth/me returns 401 without authentication."""
        response = client.get("/auth/me")
        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"
    
    def test_logout_endpoint(self):
        """Test /auth/logout clears session."""
        response = client.post("/auth/logout")
        assert response.status_code == 200
        assert response.json()["message"] == "Logged out successfully"
    
    def test_full_auth_flow_dt_manager(self):
        """Test complete authentication flow for DT manager."""
        # Step 1: Get login URL
        response = client.get("/auth/login")
        assert response.status_code == 200
        auth_url = response.json()["authorization_url"]

        # Step 2: Simulate Google OAuth login (get authorization code)
        email = "thomas.manson@croix-rouge.fr"
        code = okta_mock.create_mock_authorization_code(email)

        # Step 3: Exchange code for token via callback
        # Create a new client to properly handle cookies
        test_client = TestClient(app)
        response = test_client.get(
            f"/auth/callback?code={code}&state=test-state",
            follow_redirects=False
        )
        if response.status_code != 307:
            print(f"Error: {response.json()}")
        assert response.status_code == 307  # Redirect

        # Extract session cookie
        cookies = response.cookies
        assert auth_settings.session_cookie_name in cookies
        session_token = cookies[auth_settings.session_cookie_name]

        # Step 4: Access /auth/me with session cookie
        # Pass cookies in the request
        response = test_client.get("/auth/me", cookies={auth_settings.session_cookie_name: session_token})
        assert response.status_code == 200
        user = response.json()

        assert user["email"] == email
        assert user["role"] == "Gestionnaire DT"
        assert user["nom"] == "Manson"
        assert user["prenom"] == "Thomas"
        assert user["ul"] == "DT Paris"
    
    def test_full_auth_flow_ul_responsible(self):
        """Test complete authentication flow for UL responsible."""
        email = "claire.rousseau@croix-rouge.fr"
        code = okta_mock.create_mock_authorization_code(email)

        test_client = TestClient(app)
        response = test_client.get(
            f"/auth/callback?code={code}&state=test-state",
            follow_redirects=False
        )
        session_token = response.cookies[auth_settings.session_cookie_name]

        response = test_client.get("/auth/me", cookies={auth_settings.session_cookie_name: session_token})
        assert response.status_code == 200
        user = response.json()

        assert user["email"] == email
        assert user["role"] == "Responsable UL"
        assert user["perimetre"] == "UL Paris 15"
        assert user["type_perimetre"] == "UL"

    def test_full_auth_flow_benevole(self):
        """Test complete authentication flow for regular volunteer."""
        email = "jean.dupont@croix-rouge.fr"
        code = okta_mock.create_mock_authorization_code(email)

        test_client = TestClient(app)
        response = test_client.get(
            f"/auth/callback?code={code}&state=test-state",
            follow_redirects=False
        )
        session_token = response.cookies[auth_settings.session_cookie_name]

        response = test_client.get("/auth/me", cookies={auth_settings.session_cookie_name: session_token})
        assert response.status_code == 200
        user = response.json()

        assert user["email"] == email
        assert user["role"] == "Bénévole"
        assert user["ul"] == "UL Paris 15"
    
    def test_invalid_authorization_code(self):
        """Test callback with invalid authorization code."""
        response = client.get(
            "/auth/callback?code=invalid-code&state=test-state",
            follow_redirects=False
        )
        assert response.status_code == 400
        assert "Authentication failed" in response.json()["detail"]


class TestAuthDependencies:
    """Test authentication dependencies and guards."""

    def _get_authenticated_client(self, email: str) -> TestClient:
        """Helper to get authenticated test client."""
        code = okta_mock.create_mock_authorization_code(email)
        test_client = TestClient(app)
        response = test_client.get(
            f"/auth/callback?code={code}&state=test-state",
            follow_redirects=False
        )
        session_token = response.cookies[auth_settings.session_cookie_name]
        test_client.cookies.set(auth_settings.session_cookie_name, session_token)
        return test_client

    def test_require_authenticated_user(self):
        """Test is_authenticated dependency."""
        # Create a protected endpoint for testing
        from fastapi import APIRouter, Depends
        from app.auth.dependencies import is_authenticated

        test_router = APIRouter()

        @test_router.get("/test-protected")
        async def test_protected(user = Depends(is_authenticated)):
            return {"user": user.email}

        app.include_router(test_router)

        # Test without authentication
        response = client.get("/test-protected")
        assert response.status_code == 401

        # Test with authentication
        auth_client = self._get_authenticated_client("jean.dupont@croix-rouge.fr")
        response = auth_client.get("/test-protected")
        assert response.status_code == 200
        assert response.json()["user"] == "jean.dupont@croix-rouge.fr"

    def test_require_dt_manager(self):
        """Test is_dt_manager dependency."""
        from fastapi import APIRouter, Depends
        from app.auth.dependencies import is_dt_manager

        test_router = APIRouter()

        @test_router.get("/test-dt-only")
        async def test_dt_only(user = Depends(is_dt_manager)):
            return {"user": user.email}

        app.include_router(test_router)

        # Test with regular user (should fail)
        auth_client = self._get_authenticated_client("jean.dupont@croix-rouge.fr")
        response = auth_client.get("/test-dt-only")
        assert response.status_code == 403
        assert "DT manager access required" in response.json()["detail"]

        # Test with DT manager (should succeed)
        auth_client = self._get_authenticated_client("thomas.manson@croix-rouge.fr")
        response = auth_client.get("/test-dt-only")
        assert response.status_code == 200
        assert response.json()["user"] == "thomas.manson@croix-rouge.fr"

    def test_require_ul_responsible(self):
        """Test is_ul_responsible dependency."""
        from fastapi import APIRouter, Depends
        from app.auth.dependencies import is_ul_responsible

        test_router = APIRouter()

        @test_router.get("/test-ul-responsible")
        async def test_ul_responsible(user = Depends(is_ul_responsible)):
            return {"user": user.email}

        app.include_router(test_router)

        # Test with regular volunteer (should fail)
        auth_client = self._get_authenticated_client("jean.dupont@croix-rouge.fr")
        response = auth_client.get("/test-ul-responsible")
        assert response.status_code == 403

        # Test with UL responsible (should succeed)
        auth_client = self._get_authenticated_client("claire.rousseau@croix-rouge.fr")
        response = auth_client.get("/test-ul-responsible")
        assert response.status_code == 200

        # Test with DT manager (should also succeed)
        auth_client = self._get_authenticated_client("thomas.manson@croix-rouge.fr")
        response = auth_client.get("/test-ul-responsible")
        assert response.status_code == 200


class TestAuthService:
    """Test authentication service."""

    def test_user_role_determination_dt_manager(self):
        """Test role determination for DT manager."""
        from app.auth.service import AuthService
        from app.auth.models import TokenData

        service = AuthService()
        token_data = TokenData(
            email="thomas.manson@croix-rouge.fr",
            given_name="Thomas",
            family_name="Manson",
            sub="test-sub"
        )

        user = service.get_user_from_token(token_data)
        assert user.role == "Gestionnaire DT"
        assert user.ul == "DT Paris"
        assert service.is_dt_manager(user)
        assert service.is_ul_responsible(user)

    def test_user_role_determination_ul_responsible(self):
        """Test role determination for UL responsible."""
        from app.auth.service import AuthService
        from app.auth.models import TokenData

        service = AuthService()
        token_data = TokenData(
            email="claire.rousseau@croix-rouge.fr",
            given_name="Claire",
            family_name="Rousseau",
            sub="test-sub"
        )

        user = service.get_user_from_token(token_data)
        assert user.role == "Responsable UL"
        assert user.perimetre == "UL Paris 15"
        assert not service.is_dt_manager(user)
        assert service.is_ul_responsible(user)

    def test_user_role_determination_benevole(self):
        """Test role determination for regular volunteer."""
        from app.auth.service import AuthService
        from app.auth.models import TokenData

        service = AuthService()
        token_data = TokenData(
            email="jean.dupont@croix-rouge.fr",
            given_name="Jean",
            family_name="Dupont",
            sub="test-sub"
        )

        user = service.get_user_from_token(token_data)
        assert user.role == "Bénévole"
        assert user.ul == "UL Paris 15"
        assert not service.is_dt_manager(user)
        assert not service.is_ul_responsible(user)

