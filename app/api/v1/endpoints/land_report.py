"""Land mutation report endpoint."""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.api.deps import ReportDep
from app.infrastructure.unavailable import ResourceUnavailableError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["land", "reports"])


@router.get("/report/{id_mutation}")
async def generate_mutation_report(
    id_mutation: str,
    report_service: ReportDep,
    format: Annotated[str, Query(description="Output format: pdf or html")] = "html",
) -> Response:
    """Genere le rapport d'une mutation (libre et gratuit)."""
    try:
        content = await report_service.generate_report(id_mutation, format=format)
        if format == "pdf":
            return Response(
                content=content,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="rapport_{id_mutation}.pdf"'},
            )
        return Response(
            content=content,
            media_type="text/html",
            headers={"Content-Type": "text/html; charset=utf-8"},
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Mutation not found")
    except ResourceUnavailableError:
        # 503 explicite : donnee non chargee ou extension absente.
        # Sans cette reprise, le `except Exception` ci-dessous la
        # transformerait en 500 « erreur serveur ».
        raise
    except Exception:
        logger.exception("Report generation failed for mutation %s", id_mutation)
        raise HTTPException(status_code=500, detail="Report generation failed")
