"""Analytics domain models.

Pure domain models for market trends analysis.
No external dependencies (SOLID - Domain Purity).
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class YearlyTrend:
    """Yearly market trend data point.

    Represents aggregated market statistics for a single year.
    """
    year: int
    avg_price_m2: Decimal
    transaction_volume: int
    yoy_change_pct: Decimal | None  # None for first year in series


@dataclass
class MarketTrends:
    """Complete market trends analysis.

    Contains historical trends and calculated metrics.
    """
    location: str  # Commune name or coordinates
    trends: list[YearlyTrend]
    potential_gain_pct: Decimal
    trend_direction: str  # "bullish" | "bearish" | "stable"
    confidence_score: Decimal  # 0-10 based on data volume and R²
