"""Quality Scorer with Decay Functions.

Transforms distances into 0-10 scores using smooth decay curves.
"""

from dataclasses import dataclass
from decimal import Decimal
from math import exp

from app.services.enrichment.proximity_scorer import ProximityResult


@dataclass
class QualityScore:
    """Score for a single category."""
    category: str
    score: Decimal
    details: dict


class DecayFunction:
    """Decay functions for score calculation.

    Provides smooth transitions instead of hard cutoffs.
    """

    @staticmethod
    def exponential(distance: float, half_life: float = 500) -> float:
        """Exponential decay: score = 10 * exp(-ln(2) * distance / half_life).

        At half_life distance, score = 5
        At 2*half_life, score ≈ 2.5
        Never reaches exactly 0
        """
        if distance is None or distance < 0:
            return 0.0
        decay_rate = 0.693 / half_life  # ln(2) / half_life
        return 10.0 * exp(-decay_rate * distance)

    @staticmethod
    def linear(distance: float, max_distance: float = 2000) -> float:
        """Linear decay: score = 10 * (1 - distance/max_distance).

        Score = 10 at distance 0
        Score = 0 at max_distance
        """
        if distance is None or distance < 0:
            return 0.0
        if distance >= max_distance:
            return 0.0
        return 10.0 * (1 - distance / max_distance)

    @staticmethod
    def sigmoid(distance: float, midpoint: float = 500, steepness: float = 0.01) -> float:
        """Sigmoid decay: smooth S-curve transition.

        Score = 10 at distance 0
        Score = 5 at midpoint
        Smooth transition to 0
        """
        if distance is None or distance < 0:
            return 0.0
        return 10.0 / (1 + exp(steepness * (distance - midpoint)))


class QualityScorer:
    """Converts proximity metrics into quality scores (0-10).

    Uses decay functions for smooth score transitions.
    """

    # Decay parameters per category
    EDUCATION_HALFLIFE = 600   # Score = 5 at 600m
    TRANSPORT_HALFLIFE = 400   # Score = 5 at 400m (more critical)
    COMMERCE_HALFLIFE = 500
    ENVIRONMENT_HALFLIFE = 700
    NUISANCE_HALFLIFE = 400    # Inverse decay: score = 10 - exponential(...)

    def __init__(self, decay_type: str = "exponential") -> None:
        """Initialize with decay function type.

        Args:
            decay_type: 'exponential', 'linear', or 'sigmoid'
        """
        self._decay_type = decay_type
        self._decay = DecayFunction()

    def _apply_decay(
        self,
        distance: float | None,
        half_life: float,
    ) -> float:
        """Apply configured decay function."""
        if distance is None:
            return 0.0

        if self._decay_type == "exponential":
            return self._decay.exponential(distance, half_life)
        elif self._decay_type == "linear":
            return self._decay.linear(distance, half_life * 4)
        elif self._decay_type == "sigmoid":
            return self._decay.sigmoid(distance, half_life)
        else:
            return self._decay.exponential(distance, half_life)

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

    def score_nuisances(self, proximity: ProximityResult) -> QualityScore:
        """Calculate nuisances score.

        This is an INVERSE score:
        - Near a nuisance = High penalty = Low score
        - Far from nuisance = Low penalty = High score
        """
        # Calculate penalty using exponential decay (High near source)
        penalty = self._apply_decay(
            proximity.nearest_distance_m,
            self.NUISANCE_HALFLIFE,
        )

        # Base score is 10 minus penalty
        total = max(0, 10 - penalty)

        return QualityScore(
            category="nuisances",
            score=Decimal(str(round(total, 1))),
            details={
                "penalty": round(penalty, 2),
                "nearest_m": proximity.nearest_distance_m,
                "count_500m": proximity.count_500m,
                "types": proximity.poi_types,
                "decay_function": self._decay_type,
            },
        )

    def score_all(
        self,
        proximities: dict[str, ProximityResult],
        weights: dict[str, float] | None = None,
    ) -> dict[str, QualityScore]:
        """Score all categories and compute weighted global score."""
        if weights is None:
            weights = {
                "education": 0.25,
                "transport": 0.25,
                "commerce": 0.20,
                "environnement": 0.15,
                "nuisances": 0.15,
            }

        scores = {}

        if "education" in proximities:
            scores["education"] = self.score_education(proximities["education"])

        if "transport" in proximities:
            scores["transport"] = self.score_transport(proximities["transport"])

        if "commerce" in proximities:
            scores["commerce"] = self.score_commerce(proximities["commerce"])

        if "environnement" in proximities:
            scores["environnement"] = self.score_environment(proximities["environnement"])

        if "nuisances" in proximities:
            scores["nuisances"] = self.score_nuisances(proximities["nuisances"])

        # Calculate weighted global score
        total_weight = 0
        weighted_sum = Decimal("0")

        for category, quality in scores.items():
            weight = weights.get(category, 0.25)
            weighted_sum += quality.score * Decimal(str(weight))
            total_weight += weight

        global_score = weighted_sum / Decimal(str(total_weight)) if total_weight > 0 else Decimal("5.0")

        scores["global"] = QualityScore(
            category="global",
            score=global_score.quantize(Decimal("0.1")),
            details={"weights": weights, "decay_function": self._decay_type},
        )

        return scores
