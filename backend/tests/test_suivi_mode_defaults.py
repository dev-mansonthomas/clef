"""Tests for SuiviMode default value logic based on vehicle type."""
import pytest
from app.models.vehicle import SuiviMode, VehicleBase


class TestSuiviModeDefaults:
    """Test SuiviMode.determine_from_type() static method."""
    
    def test_vpsp_gets_prise_et_retour(self):
        """Test that VPSP vehicles get 'prise_et_retour' default."""
        result = SuiviMode.determine_from_type("VPSP")
        assert result == SuiviMode.PRISE_ET_RETOUR
    
    def test_log_gets_prise_et_retour(self):
        """Test that LOG vehicles get 'prise_et_retour' default."""
        result = SuiviMode.determine_from_type("LOG")
        assert result == SuiviMode.PRISE_ET_RETOUR
    
    def test_pcm_gets_prise_et_retour(self):
        """Test that PCM vehicles get 'prise_et_retour' default."""
        result = SuiviMode.determine_from_type("PCM")
        assert result == SuiviMode.PRISE_ET_RETOUR
    
    def test_vl_gets_prise(self):
        """Test that VL vehicles get 'prise' default."""
        result = SuiviMode.determine_from_type("VL")
        assert result == SuiviMode.PRISE
    
    def test_vsav_gets_prise(self):
        """Test that VSAV vehicles get 'prise' default."""
        result = SuiviMode.determine_from_type("VSAV")
        assert result == SuiviMode.PRISE
    
    def test_quad_gets_prise(self):
        """Test that Quad vehicles get 'prise' default."""
        result = SuiviMode.determine_from_type("Quad")
        assert result == SuiviMode.PRISE
    
    def test_case_insensitive(self):
        """Test that type matching is case-insensitive."""
        assert SuiviMode.determine_from_type("vpsp") == SuiviMode.PRISE_ET_RETOUR
        assert SuiviMode.determine_from_type("Vpsp") == SuiviMode.PRISE_ET_RETOUR
        assert SuiviMode.determine_from_type("log") == SuiviMode.PRISE_ET_RETOUR
        assert SuiviMode.determine_from_type("pcm") == SuiviMode.PRISE_ET_RETOUR
    
    def test_empty_type_gets_prise(self):
        """Test that empty type gets 'prise' default."""
        result = SuiviMode.determine_from_type("")
        assert result == SuiviMode.PRISE
    
    def test_none_type_gets_prise(self):
        """Test that None type gets 'prise' default."""
        result = SuiviMode.determine_from_type(None)
        assert result == SuiviMode.PRISE


class TestVehicleBaseDefaultSuiviMode:
    """Test that VehicleBase applies type-based defaults correctly."""
    
    def test_vpsp_without_suivi_mode_gets_default(self):
        """Test that VPSP vehicle without suivi_mode gets 'prise_et_retour'."""
        vehicle = VehicleBase(
            dt_ul="UL Test",
            immat="EF-619-AB",
            operationnel_mecanique="Dispo",
            marque="Test",
            modele="Test",
            type="VPSP",
            nom_synthetique="test-vpsp",
            carte_grise="CG123",
            nb_places="2",
            lieu_stationnement="Test"
        )
        assert vehicle.suivi_mode == SuiviMode.PRISE_ET_RETOUR
    
    def test_vl_without_suivi_mode_gets_default(self):
        """Test that VL vehicle without suivi_mode gets 'prise'."""
        vehicle = VehicleBase(
            dt_ul="UL Test",
            immat="AB-123-CD",
            operationnel_mecanique="Dispo",
            marque="Test",
            modele="Test",
            type="VL",
            nom_synthetique="test-vl",
            carte_grise="CG456",
            nb_places="5",
            lieu_stationnement="Test"
        )
        assert vehicle.suivi_mode == SuiviMode.PRISE
    
    def test_explicit_suivi_mode_is_preserved(self):
        """Test that explicitly set suivi_mode is not overridden."""
        vehicle = VehicleBase(
            dt_ul="UL Test",
            immat="EF-619-AB",
            operationnel_mecanique="Dispo",
            marque="Test",
            modele="Test",
            type="VPSP",
            nom_synthetique="test-vpsp",
            carte_grise="CG123",
            nb_places="2",
            lieu_stationnement="Test",
            suivi_mode=SuiviMode.RETOUR  # Explicitly set to RETOUR
        )
        # Should preserve the explicit value, not use type-based default
        assert vehicle.suivi_mode == SuiviMode.RETOUR
    
    def test_log_vehicle_gets_prise_et_retour(self):
        """Test that LOG vehicle gets 'prise_et_retour' default."""
        vehicle = VehicleBase(
            dt_ul="UL Test",
            immat="LOG-001",
            operationnel_mecanique="Dispo",
            marque="Test",
            modele="Test",
            type="LOG",
            nom_synthetique="test-log",
            carte_grise="CG789",
            nb_places="3",
            lieu_stationnement="Test"
        )
        assert vehicle.suivi_mode == SuiviMode.PRISE_ET_RETOUR
    
    def test_pcm_vehicle_gets_prise_et_retour(self):
        """Test that PCM vehicle gets 'prise_et_retour' default."""
        vehicle = VehicleBase(
            dt_ul="UL Test",
            immat="PCM-001",
            operationnel_mecanique="Dispo",
            marque="Test",
            modele="Test",
            type="PCM",
            nom_synthetique="test-pcm",
            carte_grise="CG999",
            nb_places="4",
            lieu_stationnement="Test"
        )
        assert vehicle.suivi_mode == SuiviMode.PRISE_ET_RETOUR

