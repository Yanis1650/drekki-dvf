"""Foncier-Express FastAPI Application.

Main entry point for the API.
"""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.deps import get_settings
from app.api.readiness import application_readiness
from app.api.v1.router import router as v1_router
from app.infrastructure.data_availability import DataUnavailableError
from app.infrastructure.duckdb_pool import close_pool, close_shared_connections
from app.infrastructure.duckdb_spatial import SpatialUnavailableError
from app.schemas import HealthResponse, ReadinessResponse
from app.services.parcel_report_service import cleanup_browser

logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Liberation des ressources longues a l'arret du processus.

    Trois choses survivaient a l'application : le Chromium de Playwright, les
    connexions DuckDB partagees, et le pool departemental. `cleanup_browser`
    existait deja mais n'etait branchee nulle part — un navigateur headless
    restait donc en vie apres chaque arret, et le conteneur ne rendait la main
    qu'au SIGKILL.
    """
    yield
    await cleanup_browser()
    close_shared_connections()
    close_pool()


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="API d'analyse foncière DVF - Méthodologie Mericskay",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS : l'API est publique et sans authentification (pas de cookie ni de
# jeton), donc `allow_credentials` reste a False. C'est ce qui autorise le
# joker "*" — la combinaison "*" + credentials est rejetee par les navigateurs.
_origins = os.getenv("CORS_ALLOW_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins.split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.exception_handler(DataUnavailableError)
async def _data_unavailable_handler(request: Request, exc: DataUnavailableError) -> JSONResponse:
    """Jeu de donnees non charge : 503 explicite plutot qu'un 500 opaque."""
    logger.warning("Donnees indisponibles sur %s : %s", request.url.path, exc)
    return JSONResponse(
        status_code=503,
        content={
            "detail": str(exc),
            "error": "data_unavailable",
            "dataset": exc.dataset,
        },
    )


@app.exception_handler(SpatialUnavailableError)
async def _spatial_unavailable_handler(
    request: Request, exc: SpatialUnavailableError
) -> JSONResponse:
    """Extension spatiale absente : 503 explicite."""
    logger.warning("Extension spatiale indisponible sur %s", request.url.path)
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc), "error": "spatial_unavailable"},
    )

# Include API routers
app.include_router(v1_router, prefix="/api")


@app.get("/", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        database="duckdb",
        version=settings.api_version,
    )


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    """Alias for health check."""
    return HealthResponse(
        status="ok",
        database="duckdb",
        version=settings.api_version,
    )


@app.get("/health/ready", response_model=ReadinessResponse, tags=["health"])
async def readiness() -> ReadinessResponse:
    """Sonde de disponibilite : fichier DuckDB lisible et tables coeur presentes."""
    return application_readiness()
