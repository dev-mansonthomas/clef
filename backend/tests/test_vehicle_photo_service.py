"""Tests for vehicle photo service."""
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

os.environ["USE_MOCKS"] = "true"

from app.services.vehicle_photo_service import VehiclePhotoService
from app.services.valkey_service import ValkeyService


class TestVehiclePhotoService:
    def setup_method(self):
        self.service = VehiclePhotoService()
        # Create a mock ValkeyService
        self.mock_valkey = MagicMock(spec=ValkeyService)
        self.mock_valkey.dt = "DT75"
        self.mock_valkey.redis = MagicMock()
    
    @pytest.mark.asyncio
    async def test_upload_photo_creates_folder_and_uploads(self):
        """Test that upload creates vehicle folder and uploads file."""
        # Mock configuration
        self.mock_valkey.redis.json().get = AsyncMock(return_value={
            "drive_folder_id": "root-folder-123"
        })
        
        with patch('app.services.vehicle_photo_service.drive_service') as mock_drive:
            mock_drive.get_or_create_folder = AsyncMock(return_value={
                "id": "vehicle-folder-123",
                "name": "AA-123-BB"
            })
            mock_drive.upload_file = AsyncMock(return_value={
                "id": "file-123",
                "webViewLink": "https://drive.google.com/file/d/file-123/view",
                "webContentLink": "https://drive.google.com/uc?id=file-123",
            })
            
            result = await self.service.upload_vehicle_photo(
                valkey_service=self.mock_valkey,
                vehicle_id="v1",
                immatriculation="AA-123-BB",
                file_content=b"fake image content",
                filename="photo.jpg",
            )
            
            assert result["uploaded"] == True
            assert result["file_id"] == "file-123"
            assert "web_view_link" in result
            mock_drive.get_or_create_folder.assert_called_once()
            mock_drive.upload_file.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_upload_photo_without_folder_config(self):
        """Test upload fails gracefully when Drive folder not configured."""
        # Mock no configuration
        self.mock_valkey.redis.json().get = AsyncMock(return_value=None)
        
        result = await self.service.upload_vehicle_photo(
            valkey_service=self.mock_valkey,
            vehicle_id="v1",
            immatriculation="AA-123-BB",
            file_content=b"fake image content",
            filename="photo.jpg",
        )
        
        assert result["uploaded"] == False
        assert "not configured" in result["error"]
    
    @pytest.mark.asyncio
    async def test_upload_photo_with_custom_type(self):
        """Test upload with custom photo type."""
        self.mock_valkey.redis.json().get = AsyncMock(return_value={
            "drive_folder_id": "root-folder-123"
        })
        
        with patch('app.services.vehicle_photo_service.drive_service') as mock_drive:
            mock_drive.get_or_create_folder = AsyncMock(return_value={
                "id": "vehicle-folder-123",
                "name": "AA-123-BB"
            })
            mock_drive.upload_file = AsyncMock(return_value={
                "id": "file-damage-123",
                "webViewLink": "https://drive.google.com/file/d/file-damage-123/view",
            })
            
            result = await self.service.upload_vehicle_photo(
                valkey_service=self.mock_valkey,
                vehicle_id="v1",
                immatriculation="AA-123-BB",
                file_content=b"fake image content",
                filename="damage.jpg",
                photo_type="damage",
            )
            
            assert result["uploaded"] == True
            # Check that filename contains photo_type
            call_args = mock_drive.upload_file.call_args
            assert "damage_" in call_args.kwargs["filename"]
    
    @pytest.mark.asyncio
    async def test_list_vehicle_photos(self):
        """Test listing photos for a vehicle."""
        self.mock_valkey.redis.json().get = AsyncMock(return_value={
            "drive_folder_id": "root-folder-123"
        })
        
        with patch('app.services.vehicle_photo_service.drive_service') as mock_drive:
            mock_drive.find_folder = AsyncMock(return_value={
                "id": "vehicle-folder-123",
                "name": "AA-123-BB"
            })
            mock_drive.list_files = AsyncMock(return_value=[
                {"id": "file-1", "name": "general_20240101_120000.jpg"},
                {"id": "file-2", "name": "damage_20240102_140000.jpg"},
            ])
            
            photos = await self.service.list_vehicle_photos(
                valkey_service=self.mock_valkey,
                immatriculation="AA-123-BB",
            )
            
            assert len(photos) == 2
            assert photos[0]["id"] == "file-1"
            mock_drive.find_folder.assert_called_once()
            mock_drive.list_files.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_photos_no_folder(self):
        """Test listing photos when vehicle folder doesn't exist."""
        self.mock_valkey.redis.json().get = AsyncMock(return_value={
            "drive_folder_id": "root-folder-123"
        })
        
        with patch('app.services.vehicle_photo_service.drive_service') as mock_drive:
            mock_drive.find_folder = AsyncMock(return_value=None)
            
            photos = await self.service.list_vehicle_photos(
                valkey_service=self.mock_valkey,
                immatriculation="AA-123-BB",
            )
            
            assert photos == []
    
    @pytest.mark.asyncio
    async def test_delete_vehicle_photo(self):
        """Test deleting a vehicle photo."""
        with patch('app.services.vehicle_photo_service.drive_service') as mock_drive:
            mock_drive.delete_file = AsyncMock(return_value=True)
            
            result = await self.service.delete_vehicle_photo(
                valkey_service=self.mock_valkey,
                file_id="file-123",
            )
            
            assert result == True
            mock_drive.delete_file.assert_called_once_with(dt_id="DT75", file_id="file-123")

