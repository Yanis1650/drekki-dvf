"""Filiation API endpoints."""

import logging
from pathlib import Path as PathLib

from fastapi import APIRouter, Depends, HTTPException, Path

from app.schemas.filiation import AncestorInfo, FiliationResponse
from app.services.filiation_service import FiliationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/filiation", tags=["filiation"])


def get_filiation_service() -> FiliationService:
    """Dependency injection for filiation service."""
    return FiliationService(duckdb_path=PathLib("./data/foncier.duckdb"))


@router.get("/{id_parcelle}", response_model=FiliationResponse)
async def get_parcel_filiation(
    id_parcelle: str = Path(
        ...,
        min_length=14,
        max_length=14,
        description="Full parcel ID (14 chars, ex: 35238000AB0123)",
    ),
    service: FiliationService = Depends(get_filiation_service),
):
    """Retrieve parcel filiation tree (administrative history).
    
    Returns the ancestor chain for a given parcel, tracing back through
    divisions, lotissements, and other cadastral operations.
    
    Args:
        id_parcelle: Full parcel ID (format: DDDCCCPPPSSNNNN)
            - DDD: department code (3 digits)
            - CCC: commune code (3 digits)
            - PPP: prefix (3 digits, usually 000)
            - SS: section (2 chars)
            - NNNN: number (4 digits)
        
    Returns:
        FiliationResponse with summary and ancestor chain
        
    Raises:
        HTTPException: 400 if invalid parcel ID format
        HTTPException: 500 if service error
    """
    # Parse parcel ID (format: 35238000AB0123)
    # Positions: [0:3]=dept, [3:6]=commune, [6:9]=prefix, [9:11]=section, [11:15]=numero

    if len(id_parcelle) != 14:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid parcel ID length: {len(id_parcelle)} (expected 14)",
        )

    try:
        code_commune = id_parcelle[3:6]  # 3-digit commune code
        section = id_parcelle[9:11]  # 2-char section
        numero = id_parcelle[11:15]  # 4-digit number

        logger.info(
            f"Fetching filiation for parcelle {id_parcelle} "
            f"(commune={code_commune}, section={section}, numero={numero})"
        )

        # Get ancestor tree
        node = service.get_ancestors(code_commune, section, numero)

        # Format for UI
        summary = service.format_filiation_summary(node)

        # Extract ancestor chain
        ancestors_chain = service.get_filiation_chain(node)
        ancestors = [
            AncestorInfo(
                id_parcelle=a["id_parcelle"],
                date_division=a["date_division"],
                nature_operation=a["nature_operation"],
            )
            for a in ancestors_chain
        ]

        return FiliationResponse(
            id_parcelle=id_parcelle,
            filiation_summary=summary,
            depth=node.depth,
            ancestors=ancestors,
        )

    except ValueError as e:
        logger.error(f"Invalid parcel ID format: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid parcel ID format: {e}")
    except Exception as e:
        logger.error(f"Error fetching filiation for {id_parcelle}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
