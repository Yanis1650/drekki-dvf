"""Enrichment service.

Aggregates multiple scorers to produce comprehensive enrichment data.
Uses PoiRepository for data and QualityScorer with decay functions.
"""

from decimal import Decimal
from pathlib import Path

from app.domain.models import EnrichmentScore
from app.repositories.poi_repository import PoiRepository
from app.services.enrichment.proximity_scorer import ProximityScorer
from app.services.enrichment.quality_scorer import QualityScorer


class EnrichmentService:
    """Service for calculating enrichment scores.

    Uses composition: ProximityScorer + QualityScorer + PoiRepository
    """

    def __init__(
        self,
        duckdb_path: Path | str = "./data/foncier.duckdb",
        decay_type: str = "exponential",
    ) -> None:
        """Initialize with optional decay type.

        Args:
            duckdb_path: Path to DuckDB database
            decay_type: 'exponential', 'linear', or 'sigmoid'
        """
        self._poi_repo = PoiRepository(db_path=duckdb_path)
        self._proximity_scorer = ProximityScorer(duckdb_path=duckdb_path)
        self._quality_scorer = QualityScorer(decay_type=decay_type)

    async def calculate_enrichment(
        self,
        latitude: float,
        longitude: float,
        parcelle_id: str | None = None,
    ) -> EnrichmentScore:
        """Calculate full enrichment score for a location.

        Args:
            latitude: WGS84 latitude
            longitude: WGS84 longitude
            parcelle_id: Optional parcelle ID for reference

        Returns:
            EnrichmentScore with all calculated scores
        """
        # Get proximities for all categories
        proximities = self._proximity_scorer.calculate_all_proximities(
            latitude, longitude
        )

        # Calculate quality scores with decay
        scores = self._quality_scorer.score_all(proximities)

        return EnrichmentScore(
            id_parcelle=parcelle_id or "unknown",
            schools_score=scores.get("education", self._default_score()).score,
            transport_score=scores.get("transport", self._default_score()).score,
            transit_score=scores.get("transit", self._default_score()).score,
            nuisances_score=scores.get("nuisances", self._default_score()).score,
            green_spaces_score=scores.get("environnement", self._default_score()).score,
            commerce_score=scores.get("commerce", self._default_score()).score,
        )

    async def calculate_enrichment_detailed(
        self,
        latitude: float,
        longitude: float,
    ) -> dict:
        """Calculate enrichment with detailed breakdown.

        Returns:
            Dict with scores and detailed breakdowns for each scorer
        """
        # Get proximities
        proximities = self._proximity_scorer.calculate_all_proximities(
            latitude, longitude
        )

        # Calculate scores with decay
        scores = self._quality_scorer.score_all(proximities)

        def _s(key: str) -> dict:
            obj = scores.get(key, self._default_score())
            return {"score": obj.score, **obj.details}

        return {
            "global_score": scores.get("global", self._default_score()).score,
            "education":     _s("education"),
            "transport":     _s("transport"),
            "transit":       _s("transit"),
            "nuisances":     _s("nuisances"),
            "environnement": _s("environnement"),
            "commerce":      _s("commerce"),
        }

    async def get_nearby_poi(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int = 1000,
        type_poi: str | None = None,
    ) -> list[dict]:
        """Get nearby POI for display or analysis."""
        return await self._poi_repo.get_poi_in_radius(
            lat=latitude,
            lon=longitude,
            radius_meters=radius_meters,
            type_poi=type_poi,
        )

    def _default_score(self):
        """Return default score object."""
        from app.services.enrichment.quality_scorer import QualityScore
        return QualityScore(
            category="default",
            score=Decimal("5.0"),
            details={},
        )
