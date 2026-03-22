"""Dépenses (expenses) API endpoints for vehicles."""
import csv
import io
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse, HTMLResponse

from app.models.repair_models import DepensesResponse
from app.auth.models import User
from app.auth.dependencies import require_authenticated_user
from app.services.valkey_dependencies import get_valkey_service
from app.services.valkey_service import ValkeyService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/{dt}/vehicles/{immat}/depenses",
    tags=["depenses"],
)


@router.get("", response_model=DepensesResponse)
async def get_depenses(
    dt: str,
    immat: str,
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service),
) -> DepensesResponse:
    """Get aggregated expenses for a vehicle, grouped by year."""
    vehicle = await valkey.get_vehicle(immat)
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{immat}' not found",
        )

    data = await valkey.get_vehicle_depenses(immat)
    return DepensesResponse(**data)


@router.get("/export")
async def export_depenses(
    dt: str,
    immat: str,
    format: str = Query("csv", pattern="^(csv|pdf)$"),
    current_user: User = Depends(require_authenticated_user),
    valkey: ValkeyService = Depends(get_valkey_service),
):
    """Export vehicle expenses as CSV or PDF."""
    vehicle = await valkey.get_vehicle(immat)
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{immat}' not found",
        )

    data = await valkey.get_vehicle_depenses(immat)

    if format == "csv":
        return _build_csv_response(immat, data)
    else:
        return _build_pdf_response(immat, data)


def _build_csv_response(immat: str, data: dict) -> StreamingResponse:
    """Build a CSV streaming response from depenses data."""
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "Date", "N° Dossier", "Description", "Fournisseur",
        "Classification", "Coût Total", "Coût CRF",
    ])

    for year_data in data["years"]:
        for f in year_data["factures"]:
            writer.writerow([
                f["date"],
                f["numero_dossier"],
                f.get("description") or "",
                f["fournisseur_nom"],
                f["classification"],
                f["montant_total"],
                f["montant_crf"],
            ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="depenses-{immat}.csv"'
        },
    )


def _build_pdf_response(immat: str, data: dict) -> HTMLResponse:
    """Build a print-friendly HTML page as PDF substitute."""
    rows_html = ""
    for year_data in data["years"]:
        rows_html += f'<tr class="year-header"><td colspan="7">Année {year_data["year"]} — {year_data["nb_dossiers"]} dossier(s) — Total: {year_data["total_cout"]:.2f}€ / CRF: {year_data["total_crf"]:.2f}€</td></tr>\n'
        for f in year_data["factures"]:
            rows_html += f'<tr><td>{f["date"]}</td><td>{f["numero_dossier"]}</td><td>{f.get("description") or ""}</td><td>{f["fournisseur_nom"]}</td><td>{f["classification"]}</td><td>{f["montant_total"]:.2f}€</td><td>{f["montant_crf"]:.2f}€</td></tr>\n'

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Dépenses {immat}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 20px; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: left; font-size: 13px; }}
th {{ background: #E30613; color: white; }}
.year-header td {{ background: #f5f5f5; font-weight: bold; }}
.totals {{ margin-top: 16px; font-weight: bold; }}
@media print {{ button {{ display: none; }} }}
</style></head><body>
<h1>Dépenses véhicule {immat}</h1>
<button onclick="window.print()">Imprimer / PDF</button>
<table><thead><tr><th>Date</th><th>N° Dossier</th><th>Description</th><th>Fournisseur</th><th>Classification</th><th>Coût Total</th><th>Coût CRF</th></tr></thead>
<tbody>{rows_html}</tbody></table>
<p class="totals">Total toutes années : {data['total_all_years_cout']:.2f}€ — CRF : {data['total_all_years_crf']:.2f}€</p>
</body></html>"""
    return HTMLResponse(content=html)

