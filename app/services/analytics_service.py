"""Analytics service for market trends analysis.

Business logic layer for calculating trend slopes and confidence scores.
"""

from decimal import Decimal
from statistics import linear_regression

from app.domain.analytics_models import MarketTrends, YearlyTrend


class AnalyticsService:
    """Service for market trends analysis and calculations."""

    def calculate_trend_slope(self, trends: list[YearlyTrend]) -> Decimal:
        """Calculate annualized growth rate from trend data.

        Uses linear regression to find the best-fit line through price data.
        Returns the slope as an annualized percentage.

        Args:
            trends: List of yearly trend data points

        Returns:
            Annualized growth rate as percentage (e.g., 5.2 for 5.2% per year)
        """
        if len(trends) < 2:
            return Decimal("0")

        # Prepare data for linear regression
        years = [float(t.year) for t in trends]
        prices = [float(t.avg_price_m2) for t in trends]

        # Calculate slope using linear regression
        try:
            slope, intercept = linear_regression(years, prices)

            # Convert slope to percentage of average price
            avg_price = sum(prices) / len(prices)
            if avg_price > 0:
                annual_growth_pct = (slope / avg_price) * 100
                return Decimal(str(round(annual_growth_pct, 2)))
        except Exception as e:
            print(f"ERROR: Linear regression failed: {e}")

        return Decimal("0")

    def assess_market_confidence(self, trends: list[YearlyTrend]) -> Decimal:
        """Calculate confidence score for trend analysis.

        Based on:
        - Data volume (more transactions = higher confidence)
        - Data consistency (fewer gaps = higher confidence)
        - Time span (longer history = higher confidence)

        Args:
            trends: List of yearly trend data points

        Returns:
            Confidence score from 0 to 10
        """
        if not trends:
            return Decimal("0")

        score = Decimal("0")

        # Factor 1: Time span (max 4 points)
        years_span = len(trends)
        if years_span >= 10:
            score += Decimal("4")
        elif years_span >= 5:
            score += Decimal("3")
        elif years_span >= 3:
            score += Decimal("2")
        else:
            score += Decimal("1")

        # Factor 2: Average transaction volume (max 4 points)
        avg_volume = sum(t.transaction_volume for t in trends) / len(trends)
        if avg_volume >= 1000:
            score += Decimal("4")
        elif avg_volume >= 500:
            score += Decimal("3")
        elif avg_volume >= 100:
            score += Decimal("2")
        else:
            score += Decimal("1")

        # Factor 3: Data consistency - no year with very low volume (max 2 points)
        min_volume = min(t.transaction_volume for t in trends)
        if min_volume >= 50:
            score += Decimal("2")
        elif min_volume >= 10:
            score += Decimal("1")

        return min(score, Decimal("10"))

    def determine_trend_direction(self, slope: Decimal) -> str:
        """Determine market trend direction from slope.

        Args:
            slope: Annualized growth rate percentage

        Returns:
            "bullish" | "bearish" | "stable"
        """
        if slope > Decimal("2"):
            return "bullish"
        elif slope < Decimal("-2"):
            return "bearish"
        else:
            return "stable"

    def build_market_trends(
        self,
        location: str,
        trends: list[YearlyTrend],
    ) -> MarketTrends:
        """Build complete market trends analysis.

        Args:
            location: Location identifier (commune name or coordinates)
            trends: List of yearly trend data

        Returns:
            Complete MarketTrends object with calculated metrics
        """
        slope = self.calculate_trend_slope(trends)
        confidence = self.assess_market_confidence(trends)
        direction = self.determine_trend_direction(slope)

        return MarketTrends(
            location=location,
            trends=trends,
            potential_gain_pct=slope,
            trend_direction=direction,
            confidence_score=confidence,
        )
