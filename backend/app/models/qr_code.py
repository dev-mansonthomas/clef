"""QR Code models for vehicle encoding/decoding."""
from pydantic import BaseModel, Field


class QrEncodeRequest(BaseModel):
    """Request model for encoding a vehicle nom_synthetique."""
    nom_synthetique: str = Field(
        ...,
        description="Vehicle synthetic name to encode",
        min_length=1
    )


class QrEncodeResponse(BaseModel):
    """Response model for QR code encoding."""
    encoded_id: str = Field(
        ...,
        description="Encoded vehicle ID for QR code"
    )
    qr_url: str = Field(
        ...,
        description="Full URL to encode in QR code"
    )


class QrDecodeRequest(BaseModel):
    """Request model for decoding a QR code."""
    encoded_id: str = Field(
        ...,
        description="Encoded vehicle ID from QR code",
        min_length=1
    )


class QrDecodeResponse(BaseModel):
    """Response model for QR code decoding."""
    nom_synthetique: str = Field(
        ...,
        description="Decoded vehicle synthetic name"
    )

