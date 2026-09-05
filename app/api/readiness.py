"""Sonde de disponibilite de la base departementale servie en production."""

from fastapi import HTTPException

from app.api.deps import get_settings
from app.infrastructure.dataset_status import inspect_dataset
from app.schemas import ReadinessResponse


def application_readiness() -> ReadinessResponse:
    """Retourne 200 uniquement si les donnees coeur sont disponibles."""
    status = inspect_dataset(get_settings().duckdb_path)
    if not status.ready:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "dataset_not_ready",
                "reason": status.reason,
                "missing_tables": status.missing_tables,
            },
        )
    return ReadinessResponse(missing_tables=[])
