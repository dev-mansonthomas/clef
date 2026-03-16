"""Photo upload models and schemas."""
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class PhotoUploadResponse(BaseModel):
    """Response model for photo upload."""
    file_id: str = Field(..., description="Google Drive file ID")
    file_name: str = Field(..., description="File name in Drive")
    web_view_link: str = Field(..., description="URL to view the file in Drive")
    web_content_link: Optional[str] = Field(None, description="URL to download the file")
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_id": "1abc123def456",
                "file_name": "2026-03-10_14-30_prise_1.jpg",
                "web_view_link": "https://drive.google.com/file/d/1abc123def456/view",
                "web_content_link": "https://drive.google.com/uc?id=1abc123def456&export=download"
            }
        }


class PhotosUploadResponse(BaseModel):
    """Response model for multiple photo uploads."""
    uploaded_photos: List[PhotoUploadResponse] = Field(..., description="List of uploaded photos")
    vehicle_nom_synthetique: str = Field(..., description="Vehicle synthetic name")
    folder_path: str = Field(..., description="Drive folder path where photos were uploaded")
    
    class Config:
        json_schema_extra = {
            "example": {
                "uploaded_photos": [
                    {
                        "file_id": "1abc123def456",
                        "file_name": "2026-03-10_14-30_prise_1.jpg",
                        "web_view_link": "https://drive.google.com/file/d/1abc123def456/view",
                        "web_content_link": "https://drive.google.com/uc?id=1abc123def456&export=download"
                    }
                ],
                "vehicle_nom_synthetique": "VSAV-PARIS15-01",
                "folder_path": "Photos/Carnet de Bord"
            }
        }

