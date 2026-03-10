"""
Pydantic models for authentication.
"""
from typing import Optional
from pydantic import BaseModel, EmailStr


class User(BaseModel):
    """User model representing an authenticated user."""
    email: EmailStr
    nom: str
    prenom: str
    ul: Optional[str] = None
    role: str  # "Gestionnaire DT", "Responsable UL", "Bénévole"
    perimetre: Optional[str] = None  # For responsables: their UL or activity
    type_perimetre: Optional[str] = None  # "DT", "UL", "Activité Spécialisée"


class TokenData(BaseModel):
    """Data extracted from JWT token."""
    email: EmailStr
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    sub: str  # Subject (user ID from Okta)


class LoginResponse(BaseModel):
    """Response from login endpoint."""
    authorization_url: str


class CallbackResponse(BaseModel):
    """Response from callback endpoint."""
    access_token: str
    token_type: str = "bearer"
    user: User

