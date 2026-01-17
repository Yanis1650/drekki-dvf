"""V1 API router aggregation."""

from fastapi import APIRouter

from app.api.v1.endpoints import analytics, filiation, land, reports, users

router = APIRouter(prefix="/v1")
router.include_router(analytics.router)
router.include_router(filiation.router)
router.include_router(land.router)
router.include_router(reports.router)
router.include_router(users.router)


