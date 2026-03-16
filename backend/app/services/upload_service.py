"""Photo upload service with image processing."""
from datetime import datetime
from typing import List, Literal, Tuple
from io import BytesIO
from PIL import Image

from app.services.drive import DriveService


class UploadService:
    """Service for uploading and processing photos."""
    
    # Maximum dimensions for photos (to reduce file size)
    MAX_WIDTH = 1920
    MAX_HEIGHT = 1920
    JPEG_QUALITY = 85
    
    def __init__(self, drive_service: DriveService):
        """
        Initialize the upload service.
        
        Args:
            drive_service: Drive service instance
        """
        self.drive_service = drive_service
    
    @staticmethod
    def compress_image(
        image_bytes: bytes,
        max_width: int = MAX_WIDTH,
        max_height: int = MAX_HEIGHT,
        quality: int = JPEG_QUALITY
    ) -> bytes:
        """
        Compress and resize an image.
        
        Args:
            image_bytes: Original image bytes
            max_width: Maximum width in pixels
            max_height: Maximum height in pixels
            quality: JPEG quality (1-100)
            
        Returns:
            Compressed image bytes
        """
        # Open image
        img = Image.open(BytesIO(image_bytes))
        
        # Convert to RGB if necessary (for PNG with transparency, etc.)
        if img.mode in ('RGBA', 'LA', 'P'):
            # Create white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Resize if needed
        if img.width > max_width or img.height > max_height:
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        
        # Save to bytes
        output = BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        return output.getvalue()
    
    @staticmethod
    def generate_photo_filename(
        timestamp: datetime,
        photo_type: Literal['prise', 'retour'],
        index: int
    ) -> str:
        """
        Generate a standardized photo filename.
        
        Format: YYYY-MM-DD_HH-MM_prise|retour_N.jpg
        
        Args:
            timestamp: Timestamp for the photo
            photo_type: Type of photo ('prise' or 'retour')
            index: Photo index (1-based)
            
        Returns:
            Formatted filename
        """
        date_str = timestamp.strftime("%Y-%m-%d")
        time_str = timestamp.strftime("%H-%M")
        return f"{date_str}_{time_str}_{photo_type}_{index}.jpg"
    
    def upload_photos(
        self,
        vehicle_drive_folder_id: str,
        photos: List[Tuple[str, bytes]],  # List of (original_filename, file_content)
        photo_type: Literal['prise', 'retour'],
        compress: bool = True
    ) -> List[dict]:
        """
        Upload photos to the vehicle's Drive folder.
        
        Args:
            vehicle_drive_folder_id: Root Drive folder ID for the vehicle
            photos: List of tuples (original_filename, file_content)
            photo_type: Type of photo ('prise' or 'retour')
            compress: Whether to compress images before upload
            
        Returns:
            List of uploaded file metadata
        """
        # Find or create Photos folder
        photos_folder = self.drive_service.find_or_create_folder(
            "Photos",
            vehicle_drive_folder_id
        )
        
        # Find or create "Carnet de Bord" subfolder
        carnet_folder = self.drive_service.find_or_create_folder(
            "Carnet de Bord",
            photos_folder["id"]
        )
        
        # Upload each photo
        uploaded_files = []
        timestamp = datetime.now()
        
        for index, (original_filename, file_content) in enumerate(photos, start=1):
            # Generate standardized filename
            new_filename = self.generate_photo_filename(timestamp, photo_type, index)
            
            # Compress if requested
            if compress:
                try:
                    file_content = self.compress_image(file_content)
                except Exception as e:
                    # If compression fails, use original
                    print(f"Warning: Failed to compress {original_filename}: {e}")
            
            # Upload to Drive
            file_metadata = self.drive_service.upload_file(
                file_name=new_filename,
                file_content=file_content,
                mime_type="image/jpeg",
                parent_id=carnet_folder["id"]
            )
            
            uploaded_files.append(file_metadata)
        
        return uploaded_files

