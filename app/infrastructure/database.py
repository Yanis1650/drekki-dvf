"""PostGIS database configuration.

SQLAlchemy 2.0 + GeoAlchemy2 for spatial data persistence.
SRID: Lambert-93 (EPSG:2154)
"""

from collections.abc import AsyncGenerator
from functools import lru_cache

from pydantic_settings import BaseSettings
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class DatabaseSettings(BaseSettings):
    """Database configuration from environment."""

    postgis_host: str = "localhost"
    postgis_port: int = 5432
    postgis_user: str = "foncier"
    postgis_password: str = "foncier_2024"
    postgis_db: str = "foncier_express"
    default_srid: int = 2154  # Lambert-93

    @property
    def database_url(self) -> str:
        """Async PostgreSQL connection URL."""
        return (
            f"postgresql+psycopg://{self.postgis_user}:{self.postgis_password}"
            f"@{self.postgis_host}:{self.postgis_port}/{self.postgis_db}"
        )

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> DatabaseSettings:
    """Cached settings instance."""
    return DatabaseSettings()


# Naming convention for constraints (SQLAlchemy best practice)
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


def create_engine(settings: DatabaseSettings | None = None):
    """Create async SQLAlchemy engine.

    Args:
        settings: Optional settings, uses cached if not provided
    """
    if settings is None:
        settings = get_settings()

    return create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


def create_session_factory(settings: DatabaseSettings | None = None) -> async_sessionmaker:
    """Create async session factory.

    Args:
        settings: Optional settings, uses cached if not provided
    """
    engine = create_engine(settings)
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


# Default session factory (for FastAPI Depends)
_session_factory: async_sessionmaker | None = None


def get_session_factory() -> async_sessionmaker:
    """Get or create session factory singleton."""
    global _session_factory
    if _session_factory is None:
        _session_factory = create_session_factory()
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database session.

    Usage:
        @app.get("/parcelles")
        async def get_parcelles(session: AsyncSession = Depends(get_session)):
            ...
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()
