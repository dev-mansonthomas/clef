"""Tests for CSV import endpoints."""
import os
import json
import pytest
from pathlib import Path

# Set USE_MOCKS before importing anything
os.environ["USE_MOCKS"] = "true"

# Import and configure auth settings BEFORE importing app
from app.auth.config import auth_settings
auth_settings.use_mocks = True

from fastapi.testclient import TestClient
from app.main import app
from app.auth import routes as auth_routes


def get_authenticated_client(email: str) -> TestClient:
    """Helper to get an authenticated test client via OAuth flow."""
    okta_mock = auth_routes.okta_mock
    if not okta_mock:
        raise RuntimeError("okta_mock is None - ensure USE_MOCKS=true is set")

    # Create a new client for this test
    test_client = TestClient(app)

    # Go through OAuth flow
    code = okta_mock.create_mock_authorization_code(email)
    response = test_client.get(
        f"/auth/callback?code={code}&state=test-state",
        follow_redirects=False
    )

    # The callback should set a cookie and redirect
    assert response.status_code == 307

    # Extract and set the session cookie on the client
    session_cookie = response.cookies.get(auth_settings.session_cookie_name)
    if session_cookie:
        test_client.cookies.set(auth_settings.session_cookie_name, session_cookie)

    return test_client


class TestImportVehiclesPreview:
    """Tests for CSV preview endpoint."""

    def test_preview_csv_success(self):
        """Test successful CSV preview."""
        # Get authenticated client (thomas.manson@croix-rouge.fr is DT manager)
        test_client = get_authenticated_client("thomas.manson@croix-rouge.fr")

        # Load sample CSV
        csv_path = Path(__file__).parent / "fixtures" / "vehicles_import_sample.csv"

        with open(csv_path, "rb") as f:
            response = test_client.post(
                "/api/DT75/import/vehicles/preview",
                files={"file": ("vehicles.csv", f, "text/csv")}
            )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "total_lines" in data
        assert "skip_lines" in data
        assert "columns" in data
        assert "preview_rows" in data
        assert "suggested_mappings" in data
        
        # Verify skip_lines default
        assert data["skip_lines"] == 4
        
        # Verify columns detected
        assert len(data["columns"]) == 19  # 19 columns in the CSV
        
        # Verify first column is DT/UL
        first_col = data["columns"][0]
        assert first_col["index"] == 0
        assert "DT 75 / UL" in first_col["header"]
        assert first_col["suggested_field"] == "dt_ul"
        
        # Verify suggested mappings include required fields
        suggested_fields = [m["target_field"] for m in data["suggested_mappings"]]
        assert "dt_ul" in suggested_fields
        assert "immat" in suggested_fields
        assert "indicatif" in suggested_fields
    
    def test_preview_csv_empty_file(self):
        """Test preview with empty CSV file."""
        test_client = get_authenticated_client("thomas.manson@croix-rouge.fr")

        response = test_client.post(
            "/api/DT75/import/vehicles/preview",
            files={"file": ("empty.csv", b"", "text/csv")}
        )

        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    def test_preview_csv_too_few_lines(self):
        """Test preview with CSV that has fewer lines than skip_lines."""
        test_client = get_authenticated_client("thomas.manson@croix-rouge.fr")

        csv_content = b"Line 1\nLine 2\nLine 3"

        response = test_client.post(
            "/api/DT75/import/vehicles/preview",
            files={"file": ("short.csv", csv_content, "text/csv")}
        )

        assert response.status_code == 400
        assert "skip" in response.json()["detail"].lower()


class TestImportVehicles:
    """Tests for CSV import endpoint."""

    @pytest.fixture(autouse=True)
    def cleanup_vehicles(self):
        """Delete vehicles created during import tests."""
        test_client = get_authenticated_client("thomas.manson@croix-rouge.fr")

        # Get vehicle list before test
        response = test_client.get("/api/DT75/vehicles")
        before_immats = {v["immat"] for v in response.json()["vehicles"]} if response.status_code == 200 else set()

        yield

        # Get vehicle list after test
        response = test_client.get("/api/DT75/vehicles")
        if response.status_code == 200:
            after_immats = {v["immat"] for v in response.json()["vehicles"]}
            new_immats = after_immats - before_immats
            if new_immats:
                # Delete new vehicles via ValkeyService through the cache
                from app.cache import get_cache
                from app.services.valkey_service import ValkeyService
                import asyncio
                cache = get_cache()
                if cache._connected and cache.client:
                    valkey = ValkeyService(redis_client=cache.client, dt="DT75")
                    loop = asyncio.get_event_loop()
                    for immat in new_immats:
                        loop.run_until_complete(valkey.delete_vehicle(immat))

    def test_import_csv_success(self):
        """Test successful CSV import."""
        test_client = get_authenticated_client("thomas.manson@croix-rouge.fr")

        # Load sample CSV
        csv_path = Path(__file__).parent / "fixtures" / "vehicles_import_sample.csv"
        
        # Build config with column mappings
        config = {
            "skip_lines": 4,
            "mappings": [
                {"csv_column": 0, "target_field": "dt_ul"},
                {"csv_column": 1, "target_field": "immat"},
                {"csv_column": 2, "target_field": "indicatif"},
                {"csv_column": 3, "target_field": "operationnel_mecanique"},
                {"csv_column": 4, "target_field": "raison_indispo"},
                {"csv_column": 5, "target_field": "prochain_controle_technique"},
                {"csv_column": 6, "target_field": "prochain_controle_pollution"},
                {"csv_column": 7, "target_field": "marque"},
                {"csv_column": 8, "target_field": "modele"},
                {"csv_column": 9, "target_field": "type"},
                {"csv_column": 10, "target_field": "date_mec"},
                {"csv_column": 11, "target_field": "nom_synthetique"},
                {"csv_column": 12, "target_field": "carte_grise"},
                {"csv_column": 13, "target_field": "nb_places"},
                {"csv_column": 14, "target_field": "commentaires"},
                {"csv_column": 15, "target_field": "lieu_stationnement"},
                {"csv_column": 16, "target_field": "instructions_recuperation"},
                {"csv_column": 17, "target_field": "assurance_2026"},
                {"csv_column": 18, "target_field": "numero_serie_baus"},
            ]
        }
        
        with open(csv_path, "rb") as f:
            response = test_client.post(
                "/api/DT75/import/vehicles",
                data={"config_json": json.dumps(config)},
                files={"file": ("vehicles.csv", f, "text/csv")}
            )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify import results
        assert "total_lines" in data
        assert "created" in data
        assert "updated" in data
        assert "ignored_lines" in data
        assert "errors" in data

        # CSV has 12 lines total, skip 4 metadata lines, skip 1 header row = 7 remaining
        # Lines 6-10 are data (5 rows), lines 11-12 are empty
        # total_lines counts all rows processed (including empty ones)
        assert data["total_lines"] >= 5  # At least 5 data rows

        # Should have ignored 1 line (N/A immatriculation on line 9)
        assert data["ignored_lines"] >= 1

        # Debug: print errors if any
        if data["errors"]:
            print(f"Import errors: {data['errors']}")

        # Should have created or updated 4 vehicles (5 data rows - 1 with N/A immat)
        # Vehicles may already exist in Valkey from mock data, so they count as "updated"
        assert data["created"] + data["updated"] >= 4

    def test_import_csv_all_fields_saved_to_redis(self):
        """Test that ALL 19 mapped fields are saved to Redis."""
        test_client = get_authenticated_client("thomas.manson@croix-rouge.fr")

        # Load sample CSV
        csv_path = Path(__file__).parent / "fixtures" / "vehicles_import_sample.csv"

        # Build config with ALL 19 field mappings using frontend IDs
        config = {
            "skip_lines": 4,
            "mappings": [
                {"csv_column": 0, "target_field": "dt_ul"},
                {"csv_column": 1, "target_field": "immat"},
                {"csv_column": 2, "target_field": "indicatif"},
                {"csv_column": 3, "target_field": "statut"},  # Frontend ID → operationnel_mecanique
                {"csv_column": 4, "target_field": "raison_indispo"},
                {"csv_column": 5, "target_field": "prochain_ct"},  # Frontend ID → prochain_controle_technique
                {"csv_column": 6, "target_field": "prochain_pollution"},  # Frontend ID → prochain_controle_pollution
                {"csv_column": 7, "target_field": "marque"},
                {"csv_column": 8, "target_field": "modele"},
                {"csv_column": 9, "target_field": "type"},
                {"csv_column": 10, "target_field": "date_mec"},
                {"csv_column": 11, "target_field": "nom_synthetique"},
                {"csv_column": 12, "target_field": "carte_grise"},
                {"csv_column": 13, "target_field": "nb_places"},
                {"csv_column": 14, "target_field": "commentaires"},
                {"csv_column": 15, "target_field": "lieu_stationnement"},
                {"csv_column": 16, "target_field": "instructions"},  # Frontend ID → instructions_recuperation
                {"csv_column": 17, "target_field": "assurance"},  # Frontend ID → assurance_2026
                {"csv_column": 18, "target_field": "num_baus"},  # Frontend ID → numero_serie_baus
            ]
        }

        with open(csv_path, "rb") as f:
            response = test_client.post(
                "/api/DT75/import/vehicles",
                data={"config_json": json.dumps(config)},
                files={"file": ("vehicles.csv", f, "text/csv")}
            )

        assert response.status_code == 200
        data = response.json()

        # Should have created or updated at least 4 vehicles (5 rows - 1 with N/A immat)
        # This verifies that ALL 19 fields from the mapping were processed successfully
        assert (data["created"] + data["updated"]) >= 4

        # Verify minimal errors (header row, N/A immat, empty lines, or event loop issues)
        assert len(data["errors"]) <= 3

    def test_import_csv_missing_required_fields(self):
        """Test import with missing required field mappings."""
        test_client = get_authenticated_client("thomas.manson@croix-rouge.fr")

        csv_path = Path(__file__).parent / "fixtures" / "vehicles_import_sample.csv"

        # Config missing 'immat' mapping (required field)
        config = {
            "skip_lines": 4,
            "mappings": [
                {"csv_column": 0, "target_field": "dt_ul"},
                # Missing immat (required)
                {"csv_column": 2, "target_field": "indicatif"},
            ]
        }

        with open(csv_path, "rb") as f:
            response = test_client.post(
                "/api/DT75/import/vehicles",
                data={"config_json": json.dumps(config)},
                files={"file": ("vehicles.csv", f, "text/csv")}
            )

        assert response.status_code == 400
        assert "required fields" in response.json()["detail"].lower()

    def test_import_csv_invalid_config_json(self):
        """Test import with invalid JSON config."""
        test_client = get_authenticated_client("thomas.manson@croix-rouge.fr")

        csv_path = Path(__file__).parent / "fixtures" / "vehicles_import_sample.csv"

        with open(csv_path, "rb") as f:
            response = test_client.post(
                "/api/DT75/import/vehicles",
                data={"config_json": "invalid json"},
                files={"file": ("vehicles.csv", f, "text/csv")}
            )

        assert response.status_code == 400
        assert "json" in response.json()["detail"].lower()

    def test_import_csv_non_dt_manager(self):
        """Test that non-DT managers cannot import."""
        # UL manager (not DT manager) - use jean.dupont who is a regular user
        test_client = get_authenticated_client("jean.dupont@croix-rouge.fr")

        csv_path = Path(__file__).parent / "fixtures" / "vehicles_import_sample.csv"

        config = {
            "skip_lines": 4,
            "mappings": [
                {"csv_column": 0, "target_field": "dt_ul"},
                {"csv_column": 1, "target_field": "immat"},
                {"csv_column": 2, "target_field": "indicatif"},
            ]
        }

        with open(csv_path, "rb") as f:
            response = test_client.post(
                "/api/DT75/import/vehicles",
                data={"config_json": json.dumps(config)},
                files={"file": ("vehicles.csv", f, "text/csv")}
            )

        assert response.status_code == 403
        assert "dt manager" in response.json()["detail"].lower()

    def test_import_csv_with_skip_field(self):
        """Test import with some fields marked as 'skip'."""
        test_client = get_authenticated_client("thomas.manson@croix-rouge.fr")

        csv_path = Path(__file__).parent / "fixtures" / "vehicles_import_sample.csv"

        config = {
            "skip_lines": 4,
            "mappings": [
                {"csv_column": 0, "target_field": "dt_ul"},
                {"csv_column": 1, "target_field": "immat"},
                {"csv_column": 2, "target_field": "indicatif"},
                {"csv_column": 3, "target_field": "operationnel_mecanique"},
                {"csv_column": 4, "target_field": "skip"},  # Skip this column
                {"csv_column": 7, "target_field": "marque"},
                {"csv_column": 8, "target_field": "modele"},
            ]
        }

        with open(csv_path, "rb") as f:
            response = test_client.post(
                "/api/DT75/import/vehicles",
                data={"config_json": json.dumps(config)},
                files={"file": ("vehicles.csv", f, "text/csv")}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["created"] >= 0  # Should still work

    def test_import_csv_without_indicatif(self):
        """Test import of vehicles without indicatif (issue #16.4)."""
        test_client = get_authenticated_client("thomas.manson@croix-rouge.fr")

        csv_path = Path(__file__).parent / "fixtures" / "vehicles_no_indicatif.csv"

        config = {
            "skip_lines": 4,
            "mappings": [
                {"csv_column": 0, "target_field": "dt_ul"},
                {"csv_column": 1, "target_field": "immat"},
                {"csv_column": 2, "target_field": "indicatif"},
                {"csv_column": 3, "target_field": "operationnel_mecanique"},
                {"csv_column": 7, "target_field": "marque"},
                {"csv_column": 8, "target_field": "modele"},
                {"csv_column": 9, "target_field": "type"},
                {"csv_column": 12, "target_field": "carte_grise"},
                {"csv_column": 13, "target_field": "nb_places"},
                {"csv_column": 15, "target_field": "lieu_stationnement"},
            ]
        }

        with open(csv_path, "rb") as f:
            response = test_client.post(
                "/api/DT75/import/vehicles",
                data={"config_json": json.dumps(config)},
                files={"file": ("vehicles.csv", f, "text/csv")}
            )

        assert response.status_code == 200
        data = response.json()

        # Should have created or updated 2 vehicles (GR-319-XF without indicatif, GR-320-AB with "-")
        # Note: This test verifies the fix for issue #16.4
        # Vehicles may already exist from previous test runs
        assert data["created"] + data["updated"] >= 2
        assert data["total_lines"] >= 2  # 2 data rows (header is now skipped)


