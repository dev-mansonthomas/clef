"""Tests for Drive service."""
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# Set USE_MOCKS before importing app to avoid Google credentials error
os.environ["USE_MOCKS"] = "true"

from app.services.drive_service import DriveService


class TestDriveService:
    """Test suite for DriveService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = DriveService()
        self.service.use_mocks = True
    
    @pytest.mark.asyncio
    async def test_upload_file_mock(self):
        """Test file upload in mock mode."""
        result = await self.service.upload_file(
            dt_id="DT75",
            file_content=b"fake image content",
            filename="photo_vehicule.jpg",
            mime_type="image/jpeg",
            parent_folder_id="folder-123",
            description="Photo du véhicule VL-001",
        )
        
        assert "id" in result
        assert result["name"] == "photo_vehicule.jpg"
        assert "webViewLink" in result
        assert result["mimeType"] == "image/jpeg"
        assert "mock-file-" in result["id"]
    
    @pytest.mark.asyncio
    async def test_create_folder_mock(self):
        """Test folder creation in mock mode."""
        result = await self.service.create_folder(
            dt_id="DT75",
            name="AA-123-BB",
            parent_folder_id="root-folder-123",
        )
        
        assert "id" in result
        assert result["name"] == "AA-123-BB"
        assert result["mimeType"] == "application/vnd.google-apps.folder"
        assert "webViewLink" in result
        assert "mock-folder-" in result["id"]
    
    @pytest.mark.asyncio
    async def test_find_folder_mock(self):
        """Test finding a folder in mock mode."""
        result = await self.service.find_folder(
            dt_id="DT75",
            name="AA-123-BB",
            parent_folder_id="root-folder-123",
        )
        
        # In mock mode, find_folder returns None
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_or_create_folder_mock(self):
        """Test get or create folder in mock mode."""
        result = await self.service.get_or_create_folder(
            dt_id="DT75",
            name="AA-123-BB",
            parent_folder_id="root-folder-123",
        )
        
        # Should create since find returns None in mock mode
        assert "id" in result
        assert result["name"] == "AA-123-BB"
        assert result["mimeType"] == "application/vnd.google-apps.folder"
    
    @pytest.mark.asyncio
    async def test_delete_file_mock(self):
        """Test file deletion in mock mode."""
        result = await self.service.delete_file(
            dt_id="DT75",
            file_id="file-123",
        )
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_list_files_mock(self):
        """Test listing files in mock mode."""
        result = await self.service.list_files(
            dt_id="DT75",
            folder_id="folder-123",
        )
        
        assert isinstance(result, list)
        assert len(result) == 2  # Mock mode returns 2 example files
        assert result[0]["name"] == "document-exemple-1.pdf"
        assert result[1]["name"] == "document-exemple-2.pdf"

    @pytest.mark.asyncio
    async def test_list_files_with_max_results_mock(self):
        """Test listing files with max_results parameter."""
        result = await self.service.list_files(
            dt_id="DT75",
            folder_id="folder-123",
            max_results=50,
        )

        assert isinstance(result, list)
        assert len(result) == 2


class TestDriveServiceWithRealAPI:
    """Test suite for DriveService with real API (mocked Google API calls)."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = DriveService()
        self.service.use_mocks = False
    
    @pytest.mark.asyncio
    async def test_upload_file_with_token(self):
        """Test file upload with real API (mocked)."""
        mock_service = MagicMock()
        mock_files = MagicMock()
        mock_create = MagicMock()
        
        mock_service.files.return_value = mock_files
        mock_files.create.return_value = mock_create
        mock_create.execute.return_value = {
            "id": "real-file-123",
            "name": "photo.jpg",
            "webViewLink": "https://drive.google.com/file/d/real-file-123/view",
            "webContentLink": "https://drive.google.com/uc?id=real-file-123",
            "mimeType": "image/jpeg",
        }
        
        with patch.object(self.service, '_get_service', new_callable=AsyncMock) as mock_get_service:
            mock_get_service.return_value = mock_service
            
            result = await self.service.upload_file(
                dt_id="DT75",
                file_content=b"test content",
                filename="photo.jpg",
                mime_type="image/jpeg",
                parent_folder_id="folder-123",
                description="Test photo",
            )
            
            assert result["id"] == "real-file-123"
            assert result["name"] == "photo.jpg"
            mock_files.create.assert_called_once()

