"""Tests for photo upload service."""
import os
import pytest
from datetime import datetime
from io import BytesIO
from PIL import Image

# Set USE_MOCKS before any imports
os.environ["USE_MOCKS"] = "true"

from app.services.upload_service import UploadService
from app.mocks.service_factory import get_drive_service


class TestUploadService:
    """Test upload service functionality."""
    
    def test_generate_photo_filename(self):
        """Test photo filename generation."""
        timestamp = datetime(2026, 3, 10, 14, 30, 0)
        
        # Test prise filename
        filename_prise = UploadService.generate_photo_filename(timestamp, 'prise', 1)
        assert filename_prise == "2026-03-10_14-30_prise_1.jpg"
        
        # Test retour filename
        filename_retour = UploadService.generate_photo_filename(timestamp, 'retour', 2)
        assert filename_retour == "2026-03-10_14-30_retour_2.jpg"
    
    def test_compress_image_jpeg(self):
        """Test JPEG image compression."""
        # Create a test image
        img = Image.new('RGB', (2000, 2000), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        original_bytes = img_bytes.getvalue()
        
        # Compress
        compressed = UploadService.compress_image(original_bytes)
        
        # Verify it's smaller
        assert len(compressed) < len(original_bytes)
        
        # Verify it's still a valid image
        compressed_img = Image.open(BytesIO(compressed))
        assert compressed_img.format == 'JPEG'
        assert compressed_img.width <= UploadService.MAX_WIDTH
        assert compressed_img.height <= UploadService.MAX_HEIGHT
    
    def test_compress_image_png_with_transparency(self):
        """Test PNG with transparency conversion."""
        # Create a PNG with transparency
        img = Image.new('RGBA', (1000, 1000), color=(255, 0, 0, 128))
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        original_bytes = img_bytes.getvalue()
        
        # Compress (should convert to JPEG with white background)
        compressed = UploadService.compress_image(original_bytes)
        
        # Verify it's a JPEG
        compressed_img = Image.open(BytesIO(compressed))
        assert compressed_img.format == 'JPEG'
        assert compressed_img.mode == 'RGB'
    
    def test_upload_photos(self):
        """Test uploading photos to Drive."""
        drive_service = get_drive_service()
        upload_service = UploadService(drive_service)
        
        # Create test images
        photos = []
        for i in range(2):
            img = Image.new('RGB', (800, 600), color='blue')
            img_bytes = BytesIO()
            img.save(img_bytes, format='JPEG')
            photos.append((f"test_photo_{i}.jpg", img_bytes.getvalue()))
        
        # Create a mock vehicle folder
        vehicle_folder = drive_service.create_folder("VSAV-PARIS15-01")
        
        # Upload photos
        uploaded_files = upload_service.upload_photos(
            vehicle_drive_folder_id=vehicle_folder["id"],
            photos=photos,
            photo_type='prise',
            compress=True
        )
        
        # Verify uploads
        assert len(uploaded_files) == 2
        for i, file_metadata in enumerate(uploaded_files, start=1):
            assert file_metadata["name"].endswith(f"_prise_{i}.jpg")
            assert "id" in file_metadata
            assert "webViewLink" in file_metadata
    
    def test_upload_photos_creates_folder_structure(self):
        """Test that upload creates Photos/Carnet de Bord folder structure."""
        drive_service = get_drive_service()
        upload_service = UploadService(drive_service)
        
        # Create test image
        img = Image.new('RGB', (800, 600), color='green')
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        photos = [("test.jpg", img_bytes.getvalue())]
        
        # Create a mock vehicle folder
        vehicle_folder = drive_service.create_folder("VL-PARIS15-02")
        
        # Upload photo
        uploaded_files = upload_service.upload_photos(
            vehicle_drive_folder_id=vehicle_folder["id"],
            photos=photos,
            photo_type='retour',
            compress=False
        )
        
        # Verify folder structure was created
        # Check Photos folder exists
        photos_folders = drive_service.list_files(
            parent_id=vehicle_folder["id"],
            query="Photos"
        )
        assert len(photos_folders) > 0
        
        # Check Carnet de Bord subfolder exists
        carnet_folders = drive_service.list_files(
            parent_id=photos_folders[0]["id"],
            query="Carnet de Bord"
        )
        assert len(carnet_folders) > 0
        
        # Verify file was uploaded to correct location
        assert len(uploaded_files) == 1
        assert uploaded_files[0]["parents"][0] == carnet_folders[0]["id"]
    
    def test_upload_photos_without_compression(self):
        """Test uploading photos without compression."""
        drive_service = get_drive_service()
        upload_service = UploadService(drive_service)
        
        # Create test image
        img = Image.new('RGB', (500, 500), color='yellow')
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        original_bytes = img_bytes.getvalue()
        photos = [("test.jpg", original_bytes)]
        
        # Create a mock vehicle folder
        vehicle_folder = drive_service.create_folder("VPSP-PARIS15-03")
        
        # Upload without compression
        uploaded_files = upload_service.upload_photos(
            vehicle_drive_folder_id=vehicle_folder["id"],
            photos=photos,
            photo_type='prise',
            compress=False
        )
        
        # Verify upload
        assert len(uploaded_files) == 1
        # Size should match original (no compression)
        assert uploaded_files[0]["size"] == len(original_bytes)

