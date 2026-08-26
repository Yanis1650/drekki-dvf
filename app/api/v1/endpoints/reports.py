"""Report generation endpoints.

Provides PDF and HTML report generation for parcels.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.api.deps import RepositoryDep, SettingsDep
from app.services.parcel_report_service import ParcelReportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


def get_parcel_report_service(
    repository: RepositoryDep,
    settings: SettingsDep,
) -> ParcelReportService:
    """Dependency for ParcelReportService with app config."""
    return ParcelReportService(
        land_repository=repository,
        duckdb_path=settings.duckdb_path,
    )


@router.get("/parcel/{parcel_id}/pdf")
async def generate_parcel_pdf_report(
    parcel_id: str,
    report_service: Annotated[ParcelReportService, Depends(get_parcel_report_service)],
) -> Response:
    """Genere le rapport PDF d'une parcelle cadastrale (libre et gratuit).

    Returns a professional PDF report including:
    - Cadastral identification
    - DVF price analysis (Mericskay methodology)
    - Densification potential (ZAN compliance)
    - Quality enrichment scores
    - Filiation timeline
    """
    try:
        logger.info("Generating PDF report for parcel %s", parcel_id)

        pdf_bytes = await report_service.generate_parcel_pdf(parcel_id)

        # Clean filename (remove special chars)
        safe_id = parcel_id.replace("/", "_").replace("\\", "_")
        filename = f"Rapport_Foncier_Express_{safe_id}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            },
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("PDF generation failed for %s", parcel_id)
        detail = str(e)
        if "executable doesn't exist" in detail.lower() or "chromium" in detail.lower():
            detail = "Playwright Chromium non installé. Exécutez : playwright install chromium"
        elif len(detail) > 200:
            detail = detail[:200] + "..."
        raise HTTPException(status_code=500, detail=detail)


@router.get("/parcel/{parcel_id}/html")
async def generate_parcel_html_preview(
    parcel_id: str,
    report_service: Annotated[ParcelReportService, Depends(get_parcel_report_service)],
) -> Response:
    """Apercu HTML du rapport parcelle (debug) — sans conversion PDF."""
    try:
        html_content = await report_service.generate_html_preview(parcel_id)

        return Response(
            content=html_content,
            media_type="text/html",
            headers={
                "Content-Type": "text/html; charset=utf-8"
            },
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"HTML preview failed for {parcel_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Preview generation failed: {str(e)}")
