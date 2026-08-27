"""Analytics endpoints for market trends analysis.

Provides historical market data and trend analysis.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import Settings, get_duckdb_pool, get_settings
from app.infrastructure.duckdb_pool import DuckDBPool
from app.infrastructure.unavailable import ResourceUnavailableError
from app.repositories.duckdb_analytics_repository import DuckDBAnalyticsRepository
from app.schemas import (
    MarketTrendsResponse,
    ParcelHistoryResponse,
    YearlyTrendResponse,
)
from app.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


def get_analytics_repository(
    settings: Annotated[Settings, Depends(get_settings)],
    pool: Annotated[DuckDBPool | None, Depends(get_duckdb_pool)],
) -> DuckDBAnalyticsRepository:
    """Dependency for analytics repository with optional pool routing."""
    return DuckDBAnalyticsRepository(settings.duckdb_path, pool=pool)


def get_analytics_service() -> AnalyticsService:
    """Dependency for analytics service."""
    return AnalyticsService()


AnalyticsRepoDep = Annotated[DuckDBAnalyticsRepository, Depends(get_analytics_repository)]
AnalyticsServiceDep = Annotated[AnalyticsService, Depends(get_analytics_service)]


@router.get("/trends", response_model=MarketTrendsResponse)
async def get_market_trends(
    repository: AnalyticsRepoDep,
    service: AnalyticsServiceDep,
    code_commune: Annotated[str | None, Query(description="INSEE commune code")] = None,
    lat: Annotated[float | None, Query(description="Latitude WGS84", ge=-90, le=90)] = None,
    lon: Annotated[float | None, Query(description="Longitude WGS84", ge=-180, le=180)] = None,
    radius: Annotated[int, Query(description="Radius in meters", ge=100, le=50000)] = 1000,
    years: Annotated[int, Query(description="Number of years to analyze", ge=1, le=20)] = 10,
) -> MarketTrendsResponse:
    """Get market trends for a location.

    Analyzes historical DVF data (2014-2025) to provide:
    - Yearly price evolution (avg price/m²)
    - Transaction volume trends
    - Year-over-year percentage changes
    - Potential investment gain based on trend slope
    - Market direction (bullish/bearish/stable)
    - Confidence score based on data quality

    **Location Parameters:**
    - Provide either `code_commune` OR (`lat` + `lon`)
    - If using coordinates, specify `radius` for area analysis

    **Methodology:**
    - Applies Mericskay filters (surface > 9m², price > 2000€)
    - Uses linear regression for trend slope calculation
    - Confidence score based on data volume and consistency
    """
    try:
        # Validate location parameters
        if code_commune is None and (lat is None or lon is None):
            raise HTTPException(
                status_code=400,
                detail="Must provide either code_commune or (lat, lon)"
            )

        if code_commune and (lat is not None or lon is not None):
            raise HTTPException(
                status_code=400,
                detail="Provide either code_commune OR coordinates, not both"
            )

        # Get trends from repository
        trends = await repository.get_market_trends(
            code_commune=code_commune,
            lat=lat,
            lon=lon,
            radius_meters=radius,
            years=years,
        )

        if not trends:
            raise HTTPException(
                status_code=404,
                detail="No market data found for this location"
            )

        # Build location identifier
        if code_commune:
            location = f"Commune {code_commune}"
        else:
            location = f"({lat:.4f}, {lon:.4f}) - {radius}m radius"

        # Calculate analytics
        market_analysis = service.build_market_trends(location, trends)

        # Convert to response model
        return MarketTrendsResponse(
            location=market_analysis.location,
            trends=[
                YearlyTrendResponse(
                    year=t.year,
                    avg_price_m2=t.avg_price_m2,
                    transaction_volume=t.transaction_volume,
                    yoy_change_pct=t.yoy_change_pct,
                )
                for t in market_analysis.trends
            ],
            potential_gain_pct=market_analysis.potential_gain_pct,
            trend_direction=market_analysis.trend_direction,
            confidence_score=market_analysis.confidence_score,
        )

    except HTTPException:
        raise
    except ResourceUnavailableError:
        # 503 explicite : donnee non chargee ou extension absente.
        # Sans cette reprise, le `except Exception` ci-dessous la
        # transformerait en 500 « erreur serveur ».
        raise
    except Exception as e:
        logger.exception("Market trends analysis failed")
        raise HTTPException(
            status_code=500,
            detail=f"Market trends analysis failed: {str(e)}"
        )


@router.get("/parcel/{parcel_id}/history", response_model=ParcelHistoryResponse)
async def get_parcel_history(
    parcel_id: str,
    repository: AnalyticsRepoDep,
    limit: Annotated[int, Query(description="Max transactions", ge=1, le=100)] = 100,
) -> ParcelHistoryResponse:
    """Get transaction history for a specific parcel.

    Returns historical sales data for MapLibre tooltips.
    Useful for understanding parcel-specific price evolution.

    Args:
        parcel_id: Cadastral parcel ID (e.g., "35238000AB0123")
        limit: Maximum number of transactions to return (default: 5)
    """
    try:
        logger.debug("Parcel history request: parcel_id=%s len=%d", parcel_id, len(parcel_id))

        transactions = await repository.get_parcel_history(parcel_id, limit)

        logger.debug("Parcel history: found %d transactions for %s", len(transactions), parcel_id)

        return ParcelHistoryResponse(
            parcel_id=parcel_id,
            transactions=transactions,
        )

    except ResourceUnavailableError:
        # 503 explicite : donnee non chargee ou extension absente.
        # Sans cette reprise, le `except Exception` ci-dessous la
        # transformerait en 500 « erreur serveur ».
        raise
    except Exception as e:
        logger.exception("Parcel history query failed for %s", parcel_id)
        raise HTTPException(
            status_code=500,
            detail=f"Parcel history query failed: {str(e)}"
        )
