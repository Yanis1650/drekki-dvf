"""Report generation endpoints.

Provides PDF and HTML report generation for parcels.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.api.deps import get_current_user_optional, get_user_repository
from app.infrastructure.models import User
from app.repositories.user_repository import UserRepository
from app.services.parcel_report_service import ParcelReportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


def get_parcel_report_service() -> ParcelReportService:
    """Dependency for ParcelReportService."""
    return ParcelReportService()


@router.get("/parcel/{parcel_id}/pdf")
async def generate_parcel_pdf_report(
    parcel_id: str,
    report_service: Annotated[ParcelReportService, Depends(get_parcel_report_service)],
    user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    user_repo: Annotated[UserRepository | None, Depends(get_user_repository)] = None,
) -> Response:
    """Generate PDF report for a cadastral parcel.
    
    Consumes 1 Credit if authenticated.
    
    Returns a professional PDF report including:
    - Cadastral identification
    - DVF price analysis (Mericskay methodology)
    - Densification potential (ZAN compliance)
    - Quality enrichment scores
    - Filiation timeline
    """
    try:
        user_id = user.id if user else "anonymous"
        logger.info(f"Generating PDF report for parcel {parcel_id} by user {user_id}")

        # Generate PDF
        pdf_bytes = await report_service.generate_parcel_pdf(parcel_id)

        # Debit 1 credit if authenticated
        if user and user_repo and user.credit_balance >= 1:
            await user_repo.update_balance(user.id, -1, f"PDF Report: {parcel_id}")
            await user_repo.session.commit()

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
        logger.error(f"PDF generation failed for {parcel_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@router.get("/parcel/{parcel_id}/html")
async def generate_parcel_html_preview(
    parcel_id: str,
    report_service: Annotated[ParcelReportService, Depends(get_parcel_report_service)],
) -> Response:
    """Generate HTML preview of the parcel report (for debugging).
    
    Does NOT consume credits. Returns rendered HTML without PDF conversion.
    """
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
