"""Tests for photo upload API endpoints."""
import pytest
from io import BytesIO
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.auth.dependencies import require_authenticated_user
from app.auth.models import User


# Mock authenticated user
def mock_authenticated_user():
    """Mock user for testing."""
    return User(
        email="test@croix-rouge.fr",
        nom="User",
        prenom="Test",
        ul="UL Paris 15",
        role="Bénévole",
        perimetre="UL Paris 15",
        type_perimetre="UL"
    )


@pytest.fixture
def client():
    """Create test client with mocked authentication."""
    app.dependency_overrides[require_authenticated_user] = mock_authenticated_user
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def create_test_image(width=800, height=600, color='red', format='JPEG'):
    """Helper to create a test image file."""
    img = Image.new('RGB', (width, height), color=color)
    img_bytes = BytesIO()
    img.save(img_bytes, format=format)
    img_bytes.seek(0)
    return img_bytes


class TestUploadAPI:
    """Test upload API endpoints."""
    
    def test_upload_single_photo(self, client):
        """Test uploading a single photo."""
        # Create test image
        test_image = create_test_image()
        
        # Upload
        response = client.post(
            "/api/upload/photos",
            data={
                "vehicle_nom_synthetique": "VSAV-PARIS15-01",
                "photo_type": "prise",
                "compress": "true"
            },
            files={
                "photos": ("test_photo.jpg", test_image, "image/jpeg")
            }
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["vehicle_nom_synthetique"] == "VSAV-PARIS15-01"
        assert data["folder_path"] == "Photos/Carnet de Bord"
        assert len(data["uploaded_photos"]) == 1
        
        photo = data["uploaded_photos"][0]
        assert photo["file_name"].endswith("_prise_1.jpg")
        assert "file_id" in photo
        assert "web_view_link" in photo
    
    def test_upload_multiple_photos(self, client):
        """Test uploading multiple photos."""
        # Create test images
        test_images = [
            ("photo1.jpg", create_test_image(color='red'), "image/jpeg"),
            ("photo2.jpg", create_test_image(color='blue'), "image/jpeg"),
            ("photo3.jpg", create_test_image(color='green'), "image/jpeg")
        ]
        
        # Upload
        response = client.post(
            "/api/upload/photos",
            data={
                "vehicle_nom_synthetique": "VSAV-PARIS15-01",
                "photo_type": "retour",
                "compress": "false"
            },
            files=[("photos", img) for img in test_images]
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert len(data["uploaded_photos"]) == 3
        
        # Verify filenames are numbered correctly
        for i, photo in enumerate(data["uploaded_photos"], start=1):
            assert photo["file_name"].endswith(f"_retour_{i}.jpg")
    
    def test_upload_photo_vehicle_not_found(self, client):
        """Test uploading photo for non-existent vehicle."""
        test_image = create_test_image()
        
        response = client.post(
            "/api/upload/photos",
            data={
                "vehicle_nom_synthetique": "NONEXISTENT-VEHICLE",
                "photo_type": "prise",
                "compress": "true"
            },
            files={
                "photos": ("test.jpg", test_image, "image/jpeg")
            }
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_upload_photo_invalid_format(self, client):
        """Test uploading invalid file format."""
        # Create a text file instead of image
        text_file = BytesIO(b"This is not an image")
        
        response = client.post(
            "/api/upload/photos",
            data={
                "vehicle_nom_synthetique": "VSAV-PARIS15-01",
                "photo_type": "prise",
                "compress": "true"
            },
            files={
                "photos": ("test.txt", text_file, "text/plain")
            }
        )
        
        assert response.status_code == 400
        assert "invalid photo format" in response.json()["detail"].lower()
    
    def test_upload_photo_no_files(self, client):
        """Test uploading without any files."""
        response = client.post(
            "/api/upload/photos",
            data={
                "vehicle_nom_synthetique": "VSAV-PARIS15-01",
                "photo_type": "prise",
                "compress": "true"
            },
            files={}
        )
        
        # FastAPI will return 422 for missing required field
        assert response.status_code == 422
    
    def test_upload_png_photo(self, client):
        """Test uploading PNG photo."""
        # Create PNG image
        test_image = create_test_image(format='PNG')
        
        response = client.post(
            "/api/upload/photos",
            data={
                "vehicle_nom_synthetique": "VSAV-PARIS15-01",
                "photo_type": "prise",
                "compress": "true"
            },
            files={
                "photos": ("test.png", test_image, "image/png")
            }
        )
        
        # Should succeed and convert to JPEG
        assert response.status_code == 200
        data = response.json()
        assert data["uploaded_photos"][0]["file_name"].endswith(".jpg")

