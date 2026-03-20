"""
Service for uploading vehicle photos to Google Drive.
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.services.drive_service import drive_service
from app.services.valkey_service import ValkeyService

logger = logging.getLogger(__name__)


class VehiclePhotoService:
    """Service for managing vehicle photos on Google Drive."""
    
    async def get_drive_folder_id(self, valkey_service: ValkeyService) -> Optional[str]:
        """Get configured Drive folder ID for DT."""
        config_key = f"{valkey_service.dt}:configuration"
        config = await valkey_service.redis.json().get(config_key)
        return config.get("drive_folder_id") if config else None
    
    async def upload_vehicle_photo(
        self,
        valkey_service: ValkeyService,
        vehicle_id: str,
        immatriculation: str,
        file_content: bytes,
        filename: str,
        mime_type: str = "image/jpeg",
        photo_type: str = "general",  # general, damage, before, after
    ) -> Dict[str, Any]:
        """
        Upload a vehicle photo to Google Drive.
        
        Creates a subfolder per vehicle (by immatriculation) if needed.
        
        Args:
            valkey_service: ValkeyService instance
            vehicle_id: Vehicle ID
            immatriculation: Vehicle plate number (used for folder name)
            file_content: Photo content as bytes
            filename: Original filename
            mime_type: MIME type
            photo_type: Type of photo (general, damage, before, after)
            
        Returns:
            Photo metadata with Drive URLs
        """
        dt_id = valkey_service.dt
        
        # Get root folder
        root_folder_id = await self.get_drive_folder_id(valkey_service)
        if not root_folder_id:
            logger.warning(f"No Drive folder configured for {dt_id}")
            return {
                "uploaded": False,
                "error": "Drive folder not configured",
            }
        
        try:
            # Get or create vehicle subfolder
            vehicle_folder = await drive_service.get_or_create_folder(
                dt_id=dt_id,
                name=immatriculation.upper().replace(" ", "-"),
                parent_folder_id=root_folder_id,
            )
            
            # Generate filename with timestamp
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            ext = filename.split(".")[-1] if "." in filename else "jpg"
            new_filename = f"{photo_type}_{timestamp}.{ext}"
            
            # Upload file
            file = await drive_service.upload_file(
                dt_id=dt_id,
                file_content=file_content,
                filename=new_filename,
                mime_type=mime_type,
                parent_folder_id=vehicle_folder["id"],
                description=f"Photo {photo_type} - {immatriculation} - {datetime.utcnow().isoformat()}",
            )
            
            return {
                "uploaded": True,
                "file_id": file["id"],
                "filename": new_filename,
                "web_view_link": file.get("webViewLink"),
                "web_content_link": file.get("webContentLink"),
                "folder_id": vehicle_folder["id"],
            }
            
        except Exception as e:
            logger.error(f"Failed to upload photo for {immatriculation}: {e}")
            return {
                "uploaded": False,
                "error": str(e),
            }
    
    async def list_vehicle_photos(
        self,
        valkey_service: ValkeyService,
        immatriculation: str,
    ) -> List[Dict[str, Any]]:
        """List all photos for a vehicle."""
        dt_id = valkey_service.dt
        root_folder_id = await self.get_drive_folder_id(valkey_service)
        if not root_folder_id:
            return []
        
        try:
            # Find vehicle folder
            vehicle_folder = await drive_service.find_folder(
                dt_id=dt_id,
                name=immatriculation.upper().replace(" ", "-"),
                parent_folder_id=root_folder_id,
            )
            
            if not vehicle_folder:
                return []
            
            # List files
            return await drive_service.list_files(
                dt_id=dt_id,
                folder_id=vehicle_folder["id"],
            )
            
        except Exception as e:
            logger.error(f"Failed to list photos for {immatriculation}: {e}")
            return []
    
    async def delete_vehicle_photo(
        self,
        valkey_service: ValkeyService,
        file_id: str,
    ) -> bool:
        """Delete a vehicle photo from Drive."""
        dt_id = valkey_service.dt
        try:
            return await drive_service.delete_file(dt_id=dt_id, file_id=file_id)
        except Exception as e:
            logger.error(f"Failed to delete photo {file_id}: {e}")
            return False


# Global instance
vehicle_photo_service = VehiclePhotoService()

