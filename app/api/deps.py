"""Dependency injection for FastAPI.

Provides service instances with proper repository dependencies.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.infrastructure.duckdb_pool import DuckDBPool, get_pool
from app.repositories import DuckDBLandRepository
from app.services import DvfAnalyzerService, MericskayStrategy
from app.services.enrichment import EnrichmentService
from app.services.report_service import ReportService


class Settings(BaseSettings):
    """Application settings from environment."""

    duckdb_path: str = "./data/dept35.duckdb"
    data_dir: str = "./data"
    multi_dept: bool = False
    # Garde-fou optionnel quand une base unique couvre plusieurs departements
    # (ex. foncier.duckdb France entiere). Vide = pas de filtre.
    dept_prefix: str | None = None
    default_srid: int = 2154  # Lambert-93
    api_title: str = "Foncier-Express API"
    api_version: str = "0.1.0"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


# --- Database Dependencies ---

def get_duckdb_pool(
    settings: Annotated[Settings, Depends(get_settings)]
) -> DuckDBPool | None:
    """Get multi-dept pool if enabled, else None (legacy single-DB)."""
    if settings.multi_dept:
        return get_pool(data_dir=settings.data_dir, legacy_path=settings.duckdb_path)
    return None


def get_repository(
    settings: Annotated[Settings, Depends(get_settings)],
    pool: Annotated[DuckDBPool | None, Depends(get_duckdb_pool)],
) -> DuckDBLandRepository:
    """Create DuckDB repository with optional multi-dept pool."""
    return DuckDBLandRepository(
        db_path=Path(settings.duckdb_path),
        pool=pool,
        dept_prefix=settings.dept_prefix,
    )


# --- Service Dependencies ---

def get_dvf_analyzer_service(
    repository: Annotated[DuckDBLandRepository, Depends(get_repository)]
) -> DvfAnalyzerService:
    """Create DVF analyzer service with dependencies."""
    return DvfAnalyzerService(
        strategy=MericskayStrategy(),
        transaction_repo=repository,
        enrichment_repo=repository,
    )


def get_enrichment_service(
    settings: Annotated[Settings, Depends(get_settings)]
) -> EnrichmentService:
    """Create Enrichment service with scorers."""
    return EnrichmentService(duckdb_path=settings.duckdb_path)


def get_report_service(
    settings: Annotated[Settings, Depends(get_settings)]
) -> ReportService:
    """Create Report service for PDF generation."""
    return ReportService(duckdb_path=settings.duckdb_path)


# Type aliases for cleaner endpoint signatures
SettingsDep = Annotated[Settings, Depends(get_settings)]
RepositoryDep = Annotated[DuckDBLandRepository, Depends(get_repository)]
DvfAnalyzerDep = Annotated[DvfAnalyzerService, Depends(get_dvf_analyzer_service)]
EnrichmentDep = Annotated[EnrichmentService, Depends(get_enrichment_service)]
ReportDep = Annotated[ReportService, Depends(get_report_service)]
