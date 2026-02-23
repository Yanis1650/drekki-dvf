"""Land and transaction endpoints.

Aggregates search, report, GeoJSON, parcelles and departments routers.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    land_departements,
    land_geojson,
    land_parcelles,
    land_report,
    land_search,
)

router = APIRouter(prefix="/land", tags=["land", "transactions"])
router.include_router(land_search.router)
router.include_router(land_report.router)
router.include_router(land_geojson.router)
router.include_router(land_parcelles.router)
router.include_router(land_departements.router)
