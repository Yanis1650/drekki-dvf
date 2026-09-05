"""V1 API router aggregation."""

from fastapi import APIRouter

from app.api.deps import get_settings
from app.api.readiness import application_readiness
from app.api.v1.endpoints import analytics, filiation, land, reports
from app.schemas import HealthResponse, ReadinessResponse

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


@router.get("/health/ready", response_model=ReadinessResponse, tags=["health"])
async def v1_readiness() -> ReadinessResponse:
    """Sonde de disponibilite de la base departementale."""
    return application_readiness()


router.include_router(analytics.router)
router.include_router(filiation.router)
router.include_router(land.router)
router.include_router(reports.router)


