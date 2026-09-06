"""Analytics API response schemas.

Pydantic models for market trends and analytics endpoints.
"""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class YearlyTrendResponse(BaseModel):
    """Yearly market trend data point."""

    year: int = Field(description="Year (e.g., 2024)")
    avg_price_m2: Decimal = Field(description="Average price per m² for the year")
    transaction_volume: int = Field(description="Number of transactions in the year")
    yoy_change_pct: Decimal | None = Field(
        default=None,
        description="Year-over-year percentage change (null for first year)"
    )


class MarketTrendsResponse(BaseModel):
    """Complete market trends analysis response."""

    location: str = Field(description="Location identifier (commune or coordinates)")
    trends: list[YearlyTrendResponse] = Field(description="Yearly trend data points")
    potential_gain_pct: Decimal = Field(
        description="Potential annual gain percentage based on trend slope"
    )
    trend_direction: str = Field(
        description="Market direction: bullish, bearish, or stable"
    )
    confidence_score: Decimal = Field(
        ge=0,
        le=10,
        description="Confidence score (0-10) based on data volume and consistency"
    )


class ParcelHistoryResponse(BaseModel):
    """Historical transaction data for a parcel."""

    parcel_id: str = Field(description="Cadastral parcel ID")
    transactions: list[dict[str, Any]] = Field(
        description="List of historical transactions (date, price, price_m2)"
    )
