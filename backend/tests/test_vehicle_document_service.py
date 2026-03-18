"""Tests for vehicle Google Drive document service."""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["USE_MOCKS"] = "true"

from app.models.valkey_models import VehicleData
from app.models.vehicle import VehicleDocumentType
from app.services.valkey_service import ValkeyService
from app.services.vehicle_document_service import VehicleDocumentService


def build_folder(name: str) -> dict:
    slug = name.lower().replace(" ", "-").replace("'", "")
    return {
        "id": f"folder-{slug}",
        "name": name,
        "webViewLink": f"https://drive.google.com/drive/folders/{slug}",
    }


class TestVehicleDocumentService:
    def setup_method(self):
        self.service = VehicleDocumentService()
        self.mock_valkey = MagicMock(spec=ValkeyService)
        self.mock_valkey.dt = "DT75"
        self.mock_valkey.redis = MagicMock()
        self.mock_valkey.set_vehicle = AsyncMock(return_value=True)
        self.vehicle = VehicleData(
            immat="AB-123-CD",
            dt="DT75",
            dt_ul="UL 04",
            indicatif="UL04-01",
            nom_synthetique="UL 04 - VL 75046 - TOYOTA YARIS",
            marque="Toyota",
            modele="Yaris",
            operationnel_mecanique="Dispo",
            type="VL",
            carte_grise="Présente",
            nb_places="5",
            lieu_stationnement="Garage UL 04",
        )
        self.mock_valkey.redis.json().get = AsyncMock(return_value={
            "drive_folder_id": "root-folder-123",
            "drive_folder_url": "https://drive.google.com/drive/folders/root-folder-123",
        })

    def folder_sequence(self) -> list[dict]:
        return [
            build_folder("Véhicules"),
            build_folder("UL 04"),
            build_folder("UL 04 - VL 75046 - TOYOTA YARIS"),
            build_folder("Carte Grise"),
            build_folder("Carte Total"),
            build_folder("Plan d'Entretien"),
            build_folder("Factures"),
            build_folder("Assurance"),
            build_folder("Controle Technique"),
            build_folder("Carnet de Bord - Documentation CRF"),
        ]

    @pytest.mark.asyncio
    async def test_get_documents_overview_returns_selected_file(self):
        self.vehicle.documents = {
            "carte_grise": {
                "file_id": "file-cg-1",
                "name": "carte-grise.pdf",
                "web_view_link": "https://drive.google.com/file/d/file-cg-1/view",
                "selected_at": "2026-03-18T10:00:00+00:00",
                "folder_id": "folder-carte-grise",
                "folder_name": "Carte Grise",
            }
        }

        with patch("app.services.vehicle_document_service.drive_service") as mock_drive:
            mock_drive.get_or_create_folder = AsyncMock(side_effect=self.folder_sequence())
            mock_drive.list_files = AsyncMock(side_effect=[
                [{
                    "id": "file-cg-1",
                    "name": "carte-grise.pdf",
                    "webViewLink": "https://drive.google.com/file/d/file-cg-1/view",
                    "mimeType": "application/pdf",
                    "createdTime": "2026-03-18T09:00:00Z",
                }],
                [],
                [],
            ])

            result = await self.service.get_documents_overview(self.mock_valkey, self.vehicle)

        assert result.configured is True
        assert result.vehicle_folder_name == "UL 04 - VL 75046 - TOYOTA YARIS"
        assert result.documents[VehicleDocumentType.CARTE_GRISE].current_file is not None
        assert result.documents[VehicleDocumentType.CARTE_GRISE].current_file.file_id == "file-cg-1"
        assert result.documents[VehicleDocumentType.CARTE_GRISE].file_count == 1
        assert result.documents[VehicleDocumentType.FACTURES].folder_name == "Factures"

    @pytest.mark.asyncio
    async def test_associate_existing_file_persists_selection(self):
        with patch("app.services.vehicle_document_service.drive_service") as mock_drive:
            mock_drive.get_or_create_folder = AsyncMock(side_effect=self.folder_sequence())
            mock_drive.list_files = AsyncMock(return_value=[{
                "id": "file-total-1",
                "name": "carte-total.pdf",
                "webViewLink": "https://drive.google.com/file/d/file-total-1/view",
                "mimeType": "application/pdf",
                "createdTime": "2026-03-18T11:00:00Z",
            }])

            result = await self.service.associate_existing_file(
                self.mock_valkey,
                self.vehicle,
                VehicleDocumentType.CARTE_TOTAL,
                "file-total-1",
            )

        assert result.current_file is not None
        assert result.current_file.file_id == "file-total-1"
        assert self.vehicle.documents["carte_total"]["file_id"] == "file-total-1"
        self.mock_valkey.set_vehicle.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upload_document_uploads_new_version_and_persists_it(self):
        with patch("app.services.vehicle_document_service.drive_service") as mock_drive:
            mock_drive.get_or_create_folder = AsyncMock(side_effect=self.folder_sequence())
            mock_drive.upload_file = AsyncMock(return_value={
                "id": "file-plan-1",
                "name": "plan_entretien.pdf",
                "webViewLink": "https://drive.google.com/file/d/file-plan-1/view",
                "mimeType": "application/pdf",
                "createdTime": "2026-03-18T12:00:00Z",
            })
            mock_drive.list_files = AsyncMock(return_value=[])

            result = await self.service.upload_document(
                self.mock_valkey,
                self.vehicle,
                VehicleDocumentType.PLAN_ENTRETIEN,
                b"fake-pdf",
                "plan_entretien.pdf",
                "application/pdf",
            )

        assert result.current_file is not None
        assert result.current_file.file_id == "file-plan-1"
        assert self.vehicle.documents["plan_entretien"]["file_id"] == "file-plan-1"
        mock_drive.upload_file.assert_awaited_once()