"""CSV import endpoints for vehicles."""
import csv
import io
import json
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from datetime import datetime

from app.models.import_models import (
    ImportConfig,
    PreviewResponse,
    ImportResult,
    ColumnInfo,
    PreviewRow,
    ColumnMapping,
    ImportError
)
from app.models.valkey_models import VehicleData
from app.auth.models import User
from app.auth.dependencies import require_authenticated_user
from app.services.valkey_dependencies import get_valkey_service
from app.services.valkey_service import ValkeyService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/{dt}/import/vehicles",
    tags=["import"]
)


# Mapping of common CSV headers to target fields
HEADER_MAPPINGS = {
    "dt 75 / ul": "dt_ul",
    "dt": "dt_ul",
    "ul": "dt_ul",
    "immat": "immat",
    "immatriculation": "immat",
    "indicatif": "indicatif",
    "opérationnel mécanique": "operationnel_mecanique",
    "operationnel mecanique": "operationnel_mecanique",
    "statut": "operationnel_mecanique",
    "raison indispo": "raison_indispo",
    "prochain controle technique": "prochain_controle_technique",
    "prochain ct": "prochain_controle_technique",
    "ct": "prochain_controle_technique",
    "prochain controle pollution": "prochain_controle_pollution",
    "pollution": "prochain_controle_pollution",
    "marque": "marque",
    "modèle": "modele",
    "modele": "modele",
    "type": "type",
    "date de mec": "date_mec",
    "date de mise en circulation": "date_mec",
    "mise en circulation": "date_mec",
    "date mec": "date_mec",
    "mec": "date_mec",
    "nom synthétique": "nom_synthetique",
    "nom synthetique": "nom_synthetique",
    "carte grise": "carte_grise",
    "# de place": "nb_places",
    "places": "nb_places",
    "commentaires": "commentaires",
    "lieu de stationnement": "lieu_stationnement",
    "stationnement": "lieu_stationnement",
    "instructions récupération": "instructions_recuperation",
    "instructions recuperation": "instructions_recuperation",
    "instructions": "instructions_recuperation",
    "assurance 2026": "assurance_2026",
    "assurance": "assurance_2026",
    "n° serie baus": "numero_serie_baus",
    "baus": "numero_serie_baus",
}

# Required fields for vehicle creation
REQUIRED_FIELDS = {"immat", "dt_ul"}

# Values that should be treated as empty/N/A
NA_VALUES = {"n/a", "#n/a", "", "na", "n.a.", "null", "none"}


def is_na_value(value: str) -> bool:
    """Check if a value should be treated as N/A."""
    return value.strip().lower() in NA_VALUES


def parse_date(date_str: str) -> str:
    """Convert various date formats to YYYY-MM-DD format.

    Supported formats:
    - DD/MM/YYYY
    - DD/MM/YY
    - DD-MM-YYYY
    - DD-MM-YY
    - YYYY-MM-DD (ISO format, returned as-is)
    """
    if not date_str or is_na_value(date_str):
        return ""

    date_str = date_str.strip()

    # Try YYYY-MM-DD format (ISO format - already correct)
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass

    # Try DD/MM/YYYY format
    try:
        dt = datetime.strptime(date_str, "%d/%m/%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass

    # Try DD/MM/YY format
    try:
        dt = datetime.strptime(date_str, "%d/%m/%y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass

    # Try DD-MM-YYYY format
    try:
        dt = datetime.strptime(date_str, "%d-%m-%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass

    # Try DD-MM-YY format
    try:
        dt = datetime.strptime(date_str, "%d-%m-%y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass

    # Return as-is if can't parse
    logger.warning(f"Could not parse date format: '{date_str}'")
    return date_str


def suggest_field_mapping(header: str) -> Optional[str]:
    """Suggest a target field based on CSV header."""
    normalized = header.strip().lower()
    return HEADER_MAPPINGS.get(normalized)


@router.post("/preview", response_model=PreviewResponse)
async def preview_csv(
    dt: str,
    file: UploadFile = File(...),
    current_user: User = Depends(require_authenticated_user)
) -> PreviewResponse:
    """
    Upload CSV and return preview with column detection and suggested mappings.
    
    Args:
        dt: DT identifier (e.g., "DT75")
        file: CSV file to preview
        current_user: Authenticated user
        
    Returns:
        Preview with detected columns and suggested mappings
        
    Raises:
        400: Invalid CSV file
    """
    # Read file content
    try:
        content = await file.read()
        text_content = content.decode('utf-8')
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read CSV file: {str(e)}"
        )
    
    # Parse CSV
    try:
        csv_reader = csv.reader(io.StringIO(text_content))
        all_rows = list(csv_reader)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse CSV: {str(e)}"
        )
    
    if not all_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file is empty"
        )
    
    total_lines = len(all_rows)
    skip_lines = 4  # Default
    
    # Detect columns from first non-skipped row (assumed to be header)
    if total_lines <= skip_lines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV file has only {total_lines} lines, cannot skip {skip_lines} lines"
        )

    # Get header row (first row after skip)
    header_row = all_rows[skip_lines] if skip_lines < len(all_rows) else []
    num_columns = len(header_row)

    # Collect sample values for each column
    sample_rows = all_rows[skip_lines + 1:skip_lines + 6]  # Next 5 rows

    columns: List[ColumnInfo] = []
    suggested_mappings: List[ColumnMapping] = []

    for col_idx in range(num_columns):
        header = header_row[col_idx] if col_idx < len(header_row) else ""
        sample_values = [
            row[col_idx] if col_idx < len(row) else ""
            for row in sample_rows
        ]

        suggested_field = suggest_field_mapping(header)

        columns.append(ColumnInfo(
            index=col_idx,
            header=header,
            sample_values=sample_values,
            suggested_field=suggested_field
        ))

        if suggested_field:
            suggested_mappings.append(ColumnMapping(
                csv_column=col_idx,
                target_field=suggested_field
            ))

    # Create preview rows
    preview_rows: List[PreviewRow] = []
    for idx, row in enumerate(sample_rows, start=skip_lines + 1):
        preview_rows.append(PreviewRow(
            line_number=idx,
            values=row
        ))

    return PreviewResponse(
        total_lines=total_lines,
        skip_lines=skip_lines,
        columns=columns,
        preview_rows=preview_rows,
        suggested_mappings=suggested_mappings
    )


@router.post("", response_model=ImportResult)
async def import_csv(
    dt: str,
    file: UploadFile = File(...),
    config_json: str = Form(..., description="JSON string of ImportConfig"),
    current_user: User = Depends(require_authenticated_user),
    valkey_service: ValkeyService = Depends(get_valkey_service)
) -> ImportResult:
    """
    Import vehicles from CSV with provided column mapping.

    Args:
        dt: DT identifier (e.g., "DT75")
        file: CSV file to import
        config: Import configuration with column mappings
        current_user: Authenticated user
        valkey_service: Valkey service instance

    Returns:
        Import result with statistics and errors

    Raises:
        400: Invalid CSV or configuration
        403: User doesn't have permission
    """
    # Only DT managers can import
    if current_user.role != "Gestionnaire DT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only DT managers can import vehicles"
        )

    # Parse config JSON
    try:
        config_dict = json.loads(config_json)
        config = ImportConfig(**config_dict)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON in config: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid config format: {str(e)}"
        )

    # Read file content
    try:
        content = await file.read()
        text_content = content.decode('utf-8')
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read CSV file: {str(e)}"
        )

    # Parse CSV
    try:
        csv_reader = csv.reader(io.StringIO(text_content))
        all_rows = list(csv_reader)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse CSV: {str(e)}"
        )

    if not all_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file is empty"
        )

    # Build mapping dictionary
    mapping_dict: Dict[str, int] = {}
    for mapping in config.mappings:
        if mapping.target_field != "skip":
            mapping_dict[mapping.target_field] = mapping.csv_column

    # Mapping frontend IDs to backend field names
    FIELD_ID_MAPPING = {
        "prochain_ct": "prochain_controle_technique",
        "prochain_pollution": "prochain_controle_pollution",
        "assurance": "assurance_2026",
        "instructions": "instructions_recuperation",
        "num_baus": "numero_serie_baus",
        "statut": "operationnel_mecanique",
    }

    # Convert frontend IDs to backend field names
    converted_mapping: Dict[str, int] = {}
    for field, col_idx in mapping_dict.items():
        backend_field = FIELD_ID_MAPPING.get(field, field)
        converted_mapping[backend_field] = col_idx
    mapping_dict = converted_mapping

    # Validate required fields are mapped
    missing_fields = REQUIRED_FIELDS - set(mapping_dict.keys())
    if missing_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Required fields not mapped: {', '.join(missing_fields)}"
        )

    # Process rows
    total_lines = 0
    ignored_lines = 0
    created = 0
    updated = 0
    errors: List[ImportError] = []

    data_rows = all_rows[config.skip_lines:]

    for idx, row in enumerate(data_rows, start=config.skip_lines + 1):
        total_lines += 1

        # Extract values based on mapping
        try:
            values = {}
            for field, col_idx in mapping_dict.items():
                value = row[col_idx] if col_idx < len(row) else ""
                values[field] = value.strip()

            # Debug logging for date_mec
            if "date_mec" in values:
                logger.info(f"Line {idx}: date_mec raw value: '{values.get('date_mec')}'")
                parsed_date = parse_date(values.get("date_mec", ""))
                logger.info(f"Line {idx}: date_mec parsed value: '{parsed_date}'")

            # Check if immatriculation is valid
            immat = values.get("immat", "")
            if is_na_value(immat):
                ignored_lines += 1
                errors.append(ImportError(
                    line_number=idx,
                    reason=f"Immatriculation N/A or empty: '{immat}'",
                    values=row
                ))
                continue

            # Check required fields
            missing = []
            for field in REQUIRED_FIELDS:
                if not values.get(field) or is_na_value(values[field]):
                    missing.append(field)

            if missing:
                ignored_lines += 1
                errors.append(ImportError(
                    line_number=idx,
                    reason=f"Missing required fields: {', '.join(missing)}",
                    values=row
                ))
                continue

            # Build vehicle data with defaults for missing fields
            # Force uppercase for immat and indicatif
            vehicle_dict = {
                "immat": values["immat"].upper() if values["immat"] else values["immat"],
                "dt": dt,
                "dt_ul": values.get("dt_ul", ""),
                "indicatif": values.get("indicatif", "").upper() if values.get("indicatif", "") else "",
                "marque": values.get("marque", ""),
                "modele": values.get("modele", ""),
                "nom_synthetique": values.get("nom_synthetique", ""),
                "operationnel_mecanique": values.get("operationnel_mecanique", "Dispo"),
                "raison_indispo": values.get("raison_indispo", ""),
                "prochain_controle_technique": parse_date(values.get("prochain_controle_technique", "")),
                "prochain_controle_pollution": parse_date(values.get("prochain_controle_pollution", "")),
                "type": values.get("type", ""),
                "date_mec": parse_date(values.get("date_mec", "")),
                "carte_grise": values.get("carte_grise", ""),
                "nb_places": values.get("nb_places", ""),
                "commentaires": values.get("commentaires", ""),
                "lieu_stationnement": values.get("lieu_stationnement", ""),
                "instructions_recuperation": values.get("instructions_recuperation", ""),
                "assurance_2026": values.get("assurance_2026", ""),
                "numero_serie_baus": values.get("numero_serie_baus", ""),
            }

            # Clean up N/A values in optional fields
            for key, value in vehicle_dict.items():
                if isinstance(value, str) and is_na_value(value):
                    vehicle_dict[key] = ""

            # Auto-generate nom_synthetique if empty
            if not vehicle_dict.get("nom_synthetique") or is_na_value(vehicle_dict.get("nom_synthetique", "")):
                # Build nom_synthetique, omitting indicatif if empty
                parts = [vehicle_dict['dt_ul']]
                if vehicle_dict.get('indicatif'):
                    parts.append(vehicle_dict['indicatif'])
                parts.append(vehicle_dict['immat'])
                vehicle_dict["nom_synthetique"] = " - ".join(parts)

            # Auto-determine suivi_mode based on vehicle type if not provided
            if "suivi_mode" not in values or not values.get("suivi_mode"):
                from app.models.vehicle import SuiviMode
                vehicle_type = vehicle_dict.get("type", "")
                suivi_mode = SuiviMode.determine_from_type(vehicle_type)
                vehicle_dict["suivi_mode"] = suivi_mode.value
            else:
                vehicle_dict["suivi_mode"] = values.get("suivi_mode", "prise")

            # Check if vehicle already exists
            existing = await valkey_service.get_vehicle(immat)

            # Create VehicleData object
            try:
                vehicle_data = VehicleData(**vehicle_dict)
            except Exception as e:
                errors.append(ImportError(
                    line_number=idx,
                    reason=f"Invalid vehicle data: {str(e)}",
                    values=row
                ))
                continue

            # Save to Valkey
            success = await valkey_service.set_vehicle(vehicle_data)

            if success:
                if existing:
                    updated += 1
                else:
                    created += 1
            else:
                errors.append(ImportError(
                    line_number=idx,
                    reason="Failed to save vehicle to database",
                    values=row
                ))

        except IndexError as e:
            errors.append(ImportError(
                line_number=idx,
                reason=f"Column index out of range: {str(e)}",
                values=row
            ))
        except Exception as e:
            logger.error(f"Error processing row {idx}: {e}", exc_info=True)
            errors.append(ImportError(
                line_number=idx,
                reason=f"Unexpected error: {str(e)}",
                values=row
            ))

    logger.info(
        f"Import completed for {dt}: {created} created, {updated} updated, "
        f"{ignored_lines} ignored, {len(errors)} errors"
    )

    return ImportResult(
        total_lines=total_lines,
        ignored_lines=ignored_lines,
        created=created,
        updated=updated,
        errors=errors
    )


