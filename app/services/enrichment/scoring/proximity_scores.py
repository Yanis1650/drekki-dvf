"""Les quatre scores monotones : plus c'est proche, mieux c'est.

Education, transport, commerce et environnement suivent tous la meme forme —
une decroissance sur la distance au plus proche, majoree de bonus de comptage
et de diversite. Les deux categories qui rompent cette regle vivent dans
`transit_nuisance_scores`.
"""

from decimal import Decimal

from app.services.enrichment.proximity_scorer import ProximityResult
from app.services.enrichment.scoring.models import QualityScore


class ProximityScoresMixin:
    """Scores dont la valeur decroit avec la distance."""

    def score_education(self, proximity: ProximityResult) -> QualityScore:
        """Calculate education score with decay.

        Factors:
        - Distance to nearest school (base score with decay)
        - Count of schools within 500m (bonus up to 1.5)
        - Diversity bonus (up to 0.5)
        """
        base_score = self._apply_decay(
            proximity.nearest_distance_m,
            self.EDUCATION_HALFLIFE,
        )

        # Count bonus (capped)
        count_bonus = min(1.5, proximity.count_500m * 0.3)
        count_bonus += min(1.0, proximity.count_1km * 0.15)

        # Diversity bonus
        diversity_bonus = min(0.5, len(proximity.poi_types) * 0.15)

        total = min(10, base_score + count_bonus + diversity_bonus)

        return QualityScore(
            category="education",
            score=Decimal(str(round(total, 1))),
            details={
                "base_score": round(base_score, 2),
                "count_bonus": round(count_bonus, 2),
                "diversity_bonus": round(diversity_bonus, 2),
                "nearest_m": proximity.nearest_distance_m,
                "count_500m": proximity.count_500m,
                "count_1km": proximity.count_1km,
                "types": proximity.poi_types,
                "decay_function": self._decay_type,
            },
        )

    def score_transport(self, proximity: ProximityResult) -> QualityScore:
        """Calculate transport score with decay.

        Transport is critical - shorter half-life means faster score drop.
        """
        base_score = self._apply_decay(
            proximity.nearest_distance_m,
            self.TRANSPORT_HALFLIFE,
        )

        # Multiple stations bonus
        count_bonus = min(1.5, proximity.count_1km * 0.4)

        # Diversity bonus (metro + bus + tram)
        diversity_bonus = min(0.5, len(proximity.poi_types) * 0.2)

        total = min(10, base_score + count_bonus + diversity_bonus)

        return QualityScore(
            category="transport",
            score=Decimal(str(round(total, 1))),
            details={
                "base_score": round(base_score, 2),
                "count_bonus": round(count_bonus, 2),
                "diversity_bonus": round(diversity_bonus, 2),
                "nearest_m": proximity.nearest_distance_m,
                "count_1km": proximity.count_1km,
                "types": proximity.poi_types,
                "decay_function": self._decay_type,
            },
        )

    def score_commerce(self, proximity: ProximityResult) -> QualityScore:
        """Calculate commerce score with decay."""
        base_score = self._apply_decay(
            proximity.nearest_distance_m,
            self.COMMERCE_HALFLIFE,
        )

        count_bonus = min(2.0, proximity.count_500m * 0.5)
        diversity_bonus = min(0.5, len(proximity.poi_types) * 0.15)

        total = min(10, base_score + count_bonus + diversity_bonus)

        return QualityScore(
            category="commerce",
            score=Decimal(str(round(total, 1))),
            details={
                "base_score": round(base_score, 2),
                "count_bonus": round(count_bonus, 2),
                "nearest_m": proximity.nearest_distance_m,
                "count_500m": proximity.count_500m,
            },
        )

    def score_environment(self, proximity: ProximityResult) -> QualityScore:
        """Calculate environment/green spaces score with decay."""
        base_score = self._apply_decay(
            proximity.nearest_distance_m,
            self.ENVIRONMENT_HALFLIFE,
        )

        # Bonus for multiple green spaces
        count_bonus = min(1.5, proximity.count_1km * 0.3)

        total = min(10, base_score + count_bonus)

        return QualityScore(
            category="environnement",
            score=Decimal(str(round(total, 1))),
            details={
                "base_score": round(base_score, 2),
                "count_bonus": round(count_bonus, 2),
                "nearest_m": proximity.nearest_distance_m,
                "count_1km": proximity.count_1km,
            },
        )
