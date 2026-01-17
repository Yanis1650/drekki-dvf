"""DVF Analyzer Service.

Main service for analyzing DVF data with injected cleaning strategy.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from app.domain.models import MutationAggregate
from app.repositories.interfaces import IEnrichmentRepository, ITransactionRepository
from app.services.cleaning_strategies.base import ICleaningStrategy


class DvfAnalyzerService:
    """Service for DVF analysis with strategy injection.

    Uses dependency injection for:
    - ICleaningStrategy: Methodology for data cleaning
    - ITransactionRepository: Data access layer
    - IEnrichmentRepository: Qualitative data access
    """

    def __init__(
        self,
        strategy: ICleaningStrategy,
        transaction_repo: ITransactionRepository,
        enrichment_repo: IEnrichmentRepository,
    ) -> None:
        self._strategy = strategy
        self._transaction_repo = transaction_repo
        self._enrichment_repo = enrichment_repo

    @property
    def strategy_name(self) -> str:
        """Current cleaning strategy name."""
        return self._strategy.name

    async def analyze_commune(
        self,
        code_commune: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, Any]:
        """Analyze DVF data for a commune.

        Returns aggregated statistics and mutations list.
        """
        mutations = await self._transaction_repo.get_mutations_by_commune(
            code_commune, date_from, date_to
        )
        stats = await self._transaction_repo.get_price_stats(
            code_commune, date_from, date_to
        )

        return {
            "code_commune": code_commune,
            "strategy": self._strategy.name,
            "date_range": {"from": date_from, "to": date_to},
            "statistics": stats,
            "mutations_count": len(mutations),
            "mutations": mutations,
        }

    async def get_price_statistics(
        self,
        code_commune: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, Decimal]:
        """Get price/m² statistics for a commune."""
        return await self._transaction_repo.get_price_stats(
            code_commune, date_from, date_to
        )

    async def get_enriched_mutations(
        self,
        code_commune: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]:
        """Get mutations enriched with qualitative scores."""
        mutations = await self._transaction_repo.get_mutations_by_commune(
            code_commune, date_from, date_to
        )

        enriched: list[dict[str, Any]] = []
        for mutation in mutations:
            # Get enrichment for first parcel
            enrichment = None
            if mutation.parcelles:
                enrichment = await self._enrichment_repo.get_enrichment_by_parcelle(
                    mutation.parcelles[0]
                )

            enriched.append({
                "mutation": mutation,
                "enrichment": enrichment,
            })

        return enriched

    async def detect_outliers(
        self,
        code_commune: str,
        threshold_sigma: float = 2.0,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[MutationAggregate]:
        """Detect price outliers using standard deviation.

        Args:
            code_commune: Commune code
            threshold_sigma: Number of std deviations for outlier detection
            date_from: Optional start date
            date_to: Optional end date

        Returns:
            List of mutations identified as outliers
        """
        mutations = await self._transaction_repo.get_mutations_by_commune(
            code_commune, date_from, date_to
        )

        if not mutations:
            return []

        # Calculate mean and std
        prices = [m.prix_m2 for m in mutations if m.prix_m2 is not None]
        if len(prices) < 3:
            return []

        mean_price = sum(prices) / len(prices)
        variance = sum((p - mean_price) ** 2 for p in prices) / len(prices)
        std_dev = variance ** Decimal("0.5")

        lower_bound = mean_price - (std_dev * Decimal(str(threshold_sigma)))
        upper_bound = mean_price + (std_dev * Decimal(str(threshold_sigma)))

        return [
            m for m in mutations
            if m.prix_m2 is not None and (m.prix_m2 < lower_bound or m.prix_m2 > upper_bound)
        ]
