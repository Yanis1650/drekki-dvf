"""Foncier-Express FastAPI Application.

Main entry point for the API.
"""

import asyncio
import sys
from contextlib import asynccontextmanager

# Fix for Windows: psycopg requires SelectorEventLoop, not ProactorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import get_settings
from app.api.v1.router import router as v1_router
from app.infrastructure.database import create_engine
from app.infrastructure.models import Base
from app.schemas import HealthResponse

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifecycle handler."""
    # Startup: Create tables
    engine = create_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Shutdown: Dispose engine
    await engine.dispose()


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="API d'analyse foncière DVF - Méthodologie Mericskay",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
