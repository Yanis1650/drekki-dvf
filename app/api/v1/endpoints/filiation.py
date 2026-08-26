"""Filiation API endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from app.api.deps import Settings, get_settings
from app.domain.filiation_models import FiliationNode
from app.schemas.filiation import (
    AncestorInfo,
    FiliationNodeResponse,
    FiliationResponse,
)
from app.services.filiation_service import FiliationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/filiation", tags=["filiation"])


def _node_to_response(node: FiliationNode) -> FiliationNodeResponse:
    parent = _node_to_response(node.parent) if node.parent else None
    op = node.nature_operation.value if node.nature_operation else None
    return FiliationNodeResponse(
        id_parcelle=node.id_parcelle,
        date_division=node.date_division,
        nature_operation=op,
        depth=node.depth,
        truncated=node.truncated,
        coherence_geo=node.coherence_geo,
        parent=parent,
    )


def _any_truncated_in_chain(node: FiliationNode) -> bool:
    cur: FiliationNode | None = node
    while cur is not None:
        if cur.truncated:
            return True
        cur = cur.parent
    return False


def get_filiation_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> FiliationService:
    """Injection : même base DuckDB que le reste de l'API."""
    return FiliationService(duckdb_path=settings.duckdb_path)


@router.get("/{id_parcelle}", response_model=FiliationResponse)
async def get_parcel_filiation(
    id_parcelle: str = Path(
        ...,
        min_length=13,
        max_length=14,
        description="Full parcel ID (13-14 chars, ex: 35238000AB0123)",
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
    # Parse parcel ID: 14 chars = comm(5)+pref(3)+sect(2)+num(4), 13 chars = sect(1)
    if len(id_parcelle) not in (13, 14):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid parcel ID length: {len(id_parcelle)} (expected 13 or 14)",
        )

    try:
        code_commune = id_parcelle[2:5]  # 3-digit commune (ex: 238 from 35238)
        if len(id_parcelle) == 14:
            section = id_parcelle[8:10]  # 2-char section
            numero = id_parcelle[10:14]   # 4-digit number
        else:  # 13 chars (section 1 char)
            section = id_parcelle[8:9]   # 1-char section
            numero = id_parcelle[9:13]   # 4-digit number

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
                coherence_geo=a.get("coherence_geo", "NON_VERIFIABLE"),
            )
            for a in ancestors_chain
        ]

        return FiliationResponse(
            id_parcelle=id_parcelle,
            filiation_summary=summary,
            depth=node.depth,
            truncated=_any_truncated_in_chain(node),
            ancestors=ancestors,
            tree=_node_to_response(node),
        )

    except ValueError as e:
        logger.error(f"Invalid parcel ID format: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid parcel ID format: {e}")
    except Exception as e:
        logger.error(f"Error fetching filiation for {id_parcelle}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
