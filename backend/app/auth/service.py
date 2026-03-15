"""
Authentication service for handling user authentication and role determination.
"""
from typing import Optional, Dict, Any
from .models import User, TokenData
from .config import auth_settings
from app.mocks.service_factory import get_sheets_service


class AuthService:
    """Service for authentication and user role determination."""
    
    def __init__(self):
        self.sheets_service = get_sheets_service()
        self.dt_manager_email = auth_settings.email_gestionnaire_dt
    
    def get_user_from_token(self, token_data: TokenData) -> User:
        """
        Create a User object from token data by looking up user info in referentials.

        Args:
            token_data: Data extracted from JWT token

        Returns:
            User object with role and UL information
        """
        email = token_data.email

        # Extract name from token or use defaults
        prenom = token_data.given_name or ""
        nom = token_data.family_name or ""

        # Check if user is DT manager (hardcoded email)
        if email.lower() == self.dt_manager_email.lower():
            return User(
                email=email,
                nom=nom,
                prenom=prenom,
                dt="DT75",  # Paris
                ul="DT Paris",
                role="Gestionnaire DT",
                perimetre="DT Paris",
                type_perimetre="DT"
            )

        # Check if user is a benevole (now includes responsables with role field)
        benevole = self._get_benevole(email)
        if benevole:
            # Map benevole.role to User.role
            user_role = "Bénévole"  # Default
            perimetre = benevole.get("ul")
            type_perimetre = "UL"

            benevole_role = benevole.get("role")
            if benevole_role == "responsable_dt":
                user_role = "Gestionnaire DT"
                perimetre = "DT Paris"
                type_perimetre = "DT"
            elif benevole_role == "responsable_ul":
                user_role = "Responsable UL"
                perimetre = benevole.get("ul")
                type_perimetre = "UL"

            return User(
                email=email,
                nom=benevole.get("nom", nom),
                prenom=benevole.get("prenom", prenom),
                dt=benevole.get("dt", "DT75"),  # Default to DT75 if not specified
                ul=benevole.get("ul"),
                role=user_role,
                perimetre=perimetre,
                type_perimetre=type_perimetre
            )

        # Fallback: check old responsables structure for backward compatibility
        responsable = self._get_responsable(email)
        if responsable:
            return User(
                email=email,
                nom=responsable.get("nom", nom),
                prenom=responsable.get("prenom", prenom),
                dt=responsable.get("dt", "DT75"),  # Default to DT75 if not specified
                ul=responsable.get("perimetre"),
                role=responsable.get("role", "Responsable"),
                perimetre=responsable.get("perimetre"),
                type_perimetre=responsable.get("type_perimetre")
            )

        # Default: unknown user (should not happen in production)
        return User(
            email=email,
            nom=nom,
            prenom=prenom,
            dt="DT75",  # Default to DT75
            ul=None,
            role="Bénévole",
            perimetre=None,
            type_perimetre=None
        )
    
    def _get_benevole(self, email: str) -> Optional[Dict[str, Any]]:
        """Get benevole data from cache."""
        try:
            return self.sheets_service.get_benevole_by_email(email)
        except Exception:
            return None
    
    def _get_responsable(self, email: str) -> Optional[Dict[str, Any]]:
        """Get responsable data from cache."""
        try:
            responsables = self.sheets_service.get_responsables()
            for resp in responsables:
                if resp.get("email", "").lower() == email.lower():
                    return resp
            return None
        except Exception:
            return None
    
    def is_dt_manager(self, user: User) -> bool:
        """Check if user is DT manager."""
        return user.role == "Gestionnaire DT"
    
    def is_ul_responsible(self, user: User) -> bool:
        """Check if user is UL responsible."""
        return user.role in ["Responsable UL", "Gestionnaire DT"]
    
    def is_authenticated(self, user: Optional[User]) -> bool:
        """Check if user is authenticated."""
        return user is not None

