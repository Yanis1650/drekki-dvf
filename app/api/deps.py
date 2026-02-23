"""Dependency injection for FastAPI.

Provides service instances with proper repository dependencies.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from pydantic_settings import BaseSettings
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import get_session
from app.infrastructure.duckdb_pool import DuckDBPool, get_pool
from app.infrastructure.models import User
from app.repositories import DuckDBLandRepository
from app.repositories.user_repository import UserRepository
from app.services import DvfAnalyzerService, MericskayStrategy
from app.services.enrichment import EnrichmentService
from app.services.payment_service import PaymentService
from app.services.report_service import ReportService


class Settings(BaseSettings):
    """Application settings from environment."""

    duckdb_path: str = "./data/foncier.duckdb"
    data_dir: str = "./data"
    multi_dept: bool = False
    default_srid: int = 2154  # Lambert-93
    api_title: str = "Foncier-Express API"
    api_version: str = "0.1.0"

    class Config:
        env_file = ".env"
        extra = "ignore"


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
    return DuckDBLandRepository(db_path=Path(settings.duckdb_path), pool=pool)


def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_session)]
) -> UserRepository:
    """Create User repository."""
    return UserRepository(session)


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


def get_payment_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)]
) -> PaymentService:
    """Create Payment service."""
    return PaymentService(user_repo)


# --- Security / User Dependencies ---

async def get_current_user_optional(
    x_user_id: Annotated[str | None, Header()] = None,
    user_repo: UserRepository = Depends(get_user_repository),
) -> User | None:
    """Get current user from header (MVP Auth)."""
    if not x_user_id:
        return None
    return await user_repo.get_by_id(x_user_id)


async def get_current_user(
    x_user_id: Annotated[str | None, Header()] = None,
    user_repo: UserRepository = Depends(get_user_repository),
) -> User:
    """Get current user, raise 401 if missing."""
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Id header",
        )

    # Try lookup by ID (UUID) first
    user = await user_repo.get_by_id(x_user_id)

    # For MVP: also try by email pattern (demo_user_123 -> demo_user_123@demo.com)
    if not user:
        user = await user_repo.get_by_email(f"{x_user_id}@demo.com")

    if not user:
        # Auto-create for demo/MVP if not exists
        user = await user_repo.create_user(email=f"{x_user_id}@demo.com")
        await user_repo.session.commit()
        await user_repo.session.refresh(user)

    return user


async def check_credits(
    user: Annotated[User, Depends(get_current_user)],
    user_repo: UserRepository = Depends(get_user_repository),
) -> User:
    """Verify user has enough credits."""
    if user.credit_balance < 1:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient credits. Please purchase a pack.",
        )
    return user


# Type aliases for cleaner endpoint signatures
SettingsDep = Annotated[Settings, Depends(get_settings)]
RepositoryDep = Annotated[DuckDBLandRepository, Depends(get_repository)]
DvfAnalyzerDep = Annotated[DvfAnalyzerService, Depends(get_dvf_analyzer_service)]
EnrichmentDep = Annotated[EnrichmentService, Depends(get_enrichment_service)]
ReportDep = Annotated[ReportService, Depends(get_report_service)]
PaymentDep = Annotated[PaymentService, Depends(get_payment_service)]
UserDep = Annotated[User, Depends(get_current_user)]
CreditCheckDep = Annotated[User, Depends(check_credits)]
