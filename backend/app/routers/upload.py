"""Photo upload API endpoints."""
from typing import List, Literal
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from app.models.upload import PhotoUploadResponse, PhotosUploadResponse
from app.auth.models import User
from app.auth.dependencies import require_authenticated_user
from app.services.upload_service import UploadService
from app.services.drive import get_drive_service
from app.mocks.service_factory import get_sheets_service


router = APIRouter(
    prefix="/api/upload",
    tags=["upload"]
)


@router.post("/photos", response_model=PhotosUploadResponse)
async def upload_photos(
    vehicle_nom_synthetique: str = Form(..., description="Vehicle synthetic name"),
    photo_type: Literal['prise', 'retour'] = Form(..., description="Type of photo (prise or retour)"),
    photos: List[UploadFile] = File(..., description="Photos to upload"),
    compress: bool = Form(True, description="Whether to compress images"),
    current_user: User = Depends(require_authenticated_user)
) -> PhotosUploadResponse:
    """
    Upload photos to a vehicle's Drive folder.
    
    Photos are uploaded to: {Vehicle Drive Folder}/Photos/Carnet de Bord/
    Filenames are standardized as: YYYY-MM-DD_HH-MM_prise|retour_N.jpg
    
    Args:
        vehicle_nom_synthetique: Unique synthetic name of the vehicle
        photo_type: Type of photo ('prise' for pickup, 'retour' for return)
        photos: List of photo files to upload
        compress: Whether to compress/resize images before upload
        current_user: Authenticated user
        
    Returns:
        List of uploaded photo metadata with Drive URLs
        
    Raises:
        404: Vehicle not found
        400: Invalid photo format or vehicle has no Drive folder configured
    """
    # Validate photo count
    if not photos or len(photos) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one photo is required"
        )
    
    # Get vehicle data
    sheets_service = get_sheets_service()
    vehicle_data = sheets_service.get_vehicule_by_nom_synthetique(vehicle_nom_synthetique)
    
    if not vehicle_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{vehicle_nom_synthetique}' not found"
        )
    
    # TODO: Get Drive folder ID from vehicle metadata
    # For now, we'll use a mock folder ID
    # In production, this should come from the "Metadata CLEF" sheet
    vehicle_drive_folder_id = vehicle_data.get("drive_folder_id")
    
    if not vehicle_drive_folder_id:
        # For mock/dev, create a mock folder ID based on vehicle name
        vehicle_drive_folder_id = f"mock-folder-{vehicle_nom_synthetique}"
    
    # Validate photo formats
    allowed_types = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
    for photo in photos:
        if photo.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid photo format: {photo.content_type}. Allowed: {', '.join(allowed_types)}"
            )
    
    # Read photo contents
    photo_data = []
    for photo in photos:
        content = await photo.read()
        photo_data.append((photo.filename, content))
    
    # Upload photos
    drive_service = get_drive_service()
    upload_service = UploadService(drive_service)
    
    try:
        uploaded_files = upload_service.upload_photos(
            vehicle_drive_folder_id=vehicle_drive_folder_id,
            photos=photo_data,
            photo_type=photo_type,
            compress=compress
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload photos: {str(e)}"
        )
    
    # Format response
    uploaded_photos = [
        PhotoUploadResponse(
            file_id=file["id"],
            file_name=file["name"],
            web_view_link=file["webViewLink"],
            web_content_link=file.get("webContentLink")
        )
        for file in uploaded_files
    ]
    
    return PhotosUploadResponse(
        uploaded_photos=uploaded_photos,
        vehicle_nom_synthetique=vehicle_nom_synthetique,
        folder_path="Photos/Carnet de Bord"
    )

