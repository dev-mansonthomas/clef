"""Models for CSV import functionality."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ColumnMapping(BaseModel):
    """Mapping between CSV column index and target field."""
    csv_column: int = Field(..., description="Index of the CSV column (0-based)")
    target_field: str = Field(..., description="Target Valkey field name or 'skip'")
    
    class Config:
        json_schema_extra = {
            "example": {
                "csv_column": 0,
                "target_field": "dt_ul"
            }
        }


class ImportConfig(BaseModel):
    """Configuration for CSV import."""
    skip_lines: int = Field(default=4, description="Number of lines to skip at the beginning")
    mappings: List[ColumnMapping] = Field(..., description="Column mappings")
    
    class Config:
        json_schema_extra = {
            "example": {
                "skip_lines": 4,
                "mappings": [
                    {"csv_column": 0, "target_field": "dt_ul"},
                    {"csv_column": 1, "target_field": "immat"},
                    {"csv_column": 2, "target_field": "indicatif"}
                ]
            }
        }


class PreviewRow(BaseModel):
    """A single row in the preview."""
    line_number: int = Field(..., description="Line number in the CSV file")
    values: List[str] = Field(..., description="Column values")


class ColumnInfo(BaseModel):
    """Information about a detected column."""
    index: int = Field(..., description="Column index (0-based)")
    header: Optional[str] = Field(None, description="Detected header name")
    sample_values: List[str] = Field(..., description="Sample values from first rows")
    suggested_field: Optional[str] = Field(None, description="Suggested target field based on header")


class PreviewResponse(BaseModel):
    """Response for CSV preview endpoint."""
    total_lines: int = Field(..., description="Total number of lines in the file")
    skip_lines: int = Field(..., description="Number of lines to skip (default: 4)")
    columns: List[ColumnInfo] = Field(..., description="Detected columns with sample data")
    preview_rows: List[PreviewRow] = Field(..., description="First few rows for preview")
    suggested_mappings: List[ColumnMapping] = Field(..., description="Suggested column mappings")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_lines": 25,
                "skip_lines": 4,
                "columns": [
                    {
                        "index": 0,
                        "header": "DT 75 / UL",
                        "sample_values": ["UL Paris 15", "UL Paris 16"],
                        "suggested_field": "dt_ul"
                    }
                ],
                "preview_rows": [
                    {"line_number": 5, "values": ["UL Paris 15", "AB-123-CD", "VPSU 81"]}
                ],
                "suggested_mappings": [
                    {"csv_column": 0, "target_field": "dt_ul"}
                ]
            }
        }


class ImportError(BaseModel):
    """An error that occurred during import."""
    line_number: int = Field(..., description="Line number where error occurred")
    reason: str = Field(..., description="Error reason")
    values: Optional[List[str]] = Field(None, description="Row values that caused the error")


class ImportResult(BaseModel):
    """Result of CSV import operation."""
    total_lines: int = Field(..., description="Total lines processed")
    ignored_lines: int = Field(..., description="Lines ignored (empty immat, N/A, etc.)")
    created: int = Field(..., description="Number of vehicles created")
    updated: int = Field(..., description="Number of vehicles updated")
    errors: List[ImportError] = Field(default_factory=list, description="List of errors")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_lines": 20,
                "ignored_lines": 2,
                "created": 15,
                "updated": 3,
                "errors": [
                    {
                        "line_number": 6,
                        "reason": "Immatriculation N/A",
                        "values": ["UL Paris 15", "N/A", "VPSU 81"]
                    }
                ]
            }
        }

