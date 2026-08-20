"""
Authentication service for handling user authentication and role determination.

Le référentiel des bénévoles est lu dans **Redis**, pas dans Google Sheets : tâche N2
de la décision D4. Sheets reste la source *en amont*, mais le pont est l'Apps Script
de synchronisation (`routers/sync.py`), pas une lecture directe sur le chemin
d'authentification. Voir ADR 0002 et le constat M31.
"""
import logging
from typing import Optional, Dict, Any

from .models import User, TokenData
from .config import auth_settings

logger = logging.getLogger(__name__)


class AuthService:
    """Service for authentication and user role determination."""

    def __init__(self):
        self.dt_manager_email = auth_settings.email_gestionnaire_dt

    async def get_user_from_token(self, token_data: TokenData, redis_store) -> User:
        """
        Create a User object from token data by looking up user info in referentials.

        Args:
            token_data: Data extracted from JWT token
            redis_store: `RedisService` de la délégation, source du référentiel

        Returns:
            User object with role and UL information

        Raises:
            Toute exception du datastore est **propagée**. C'est délibéré : une panne
            d'infrastructure ne doit pas se déguiser en « utilisateur sans droits ».
            L'appelant la transforme en échec d'authentification (401), après log.
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

        # Le référentiel Redis porte les bénévoles ET les responsables, ces derniers
        # étant distingués par leur champ `role` (migration Wave 11).
        benevole = await redis_store.get_benevole_by_email(email)
        if benevole:
            user_role = "Bénévole"  # Default
            perimetre = benevole.ul
            type_perimetre = "UL"

            if benevole.role == "responsable_dt":
                user_role = "Gestionnaire DT"
                perimetre = "DT Paris"
                type_perimetre = "DT"
            elif benevole.role == "responsable_ul":
                user_role = "Responsable UL"
                perimetre = benevole.ul
                type_perimetre = "UL"

            return User(
                email=email,
                nom=benevole.nom or nom,
                prenom=benevole.prenom or prenom,
                dt=benevole.dt,
                ul=benevole.ul,
                role=user_role,
                perimetre=perimetre,
                type_perimetre=type_perimetre
            )

        # Repli : email inconnu du référentiel. Volontairement *fail-closed* — aucun
        # périmètre, donc aucun droit, plutôt qu'un rôle par défaut. Journalisé, car
        # c'est le symptôme d'un référentiel non synchronisé autant que d'un accès
        # illégitime.
        logger.warning(
            "Email authentifié absent du référentiel %s : aucun périmètre accordé "
            "(email=%s)",
            getattr(redis_store, "dt", "?"),
            email,
        )
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
    
    def is_dt_manager(self, user: User) -> bool:
        """Check if user is DT manager."""
        return user.role == "Gestionnaire DT"
    
    def is_ul_responsible(self, user: User) -> bool:
        """Check if user is UL responsible."""
        return user.role in ["Responsable UL", "Gestionnaire DT"]
    
    def is_authenticated(self, user: Optional[User]) -> bool:
        """Check if user is authenticated."""
        return user is not None

