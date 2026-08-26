"""V1 API router aggregation."""

from fastapi import APIRouter

from app.api.deps import get_settings
from app.api.v1.endpoints import analytics, filiation, land, reports, users
from app.schemas import HealthResponse

router = APIRouter(prefix="/v1")


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def v1_health() -> HealthResponse:
    """Santé API v1 (même contrat que /health racine)."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        database="duckdb",
        version=settings.api_version,
    )


router.include_router(analytics.router)
router.include_router(filiation.router)
router.include_router(land.router)
router.include_router(reports.router)
router.include_router(users.router)


