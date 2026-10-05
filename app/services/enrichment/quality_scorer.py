"""Quality Scorer with Decay Functions.

Transforms distances into 0-10 scores using smooth decay curves.

Les six scores de categorie vivent dans `scoring/`, separes selon qu'ils
decroissent avec la distance (`proximity_scores`) ou non
(`transit_nuisance_scores`). Ce module garde les parametres, le choix de la
courbe et l'agregation ponderee.
"""

from decimal import Decimal

from app.services.enrichment.proximity_scorer import ProximityResult
from app.services.enrichment.scoring import (
    DecayFunction,
    ProximityScoresMixin,
    QualityScore,
    TransitNuisanceScoresMixin,
)

__all__ = ["DecayFunction", "QualityScore", "QualityScorer"]


class QualityScorer(ProximityScoresMixin, TransitNuisanceScoresMixin):
    """Converts proximity metrics into quality scores (0-10).

    Uses decay functions for smooth score transitions.
    """

    # Decay parameters per category
    EDUCATION_HALFLIFE = 600   # Score = 5 at 600m
    TRANSPORT_HALFLIFE = 400   # Score = 5 at 400m (bus/vélo)
    COMMERCE_HALFLIFE = 500
    ENVIRONMENT_HALFLIFE = 700
    NUISANCE_HALFLIFE = 400    # Inverse decay: score = 10 - exponential(...)
    # Transit TOD : gaussienne centrée sur 600m, σ=300m
    TRANSIT_PEAK = 600         # Distance optimale en mètres
    TRANSIT_SIGMA = 300        # Écart-type de la cloche

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

    def score_all(
        self,
        proximities: dict[str, ProximityResult],
        weights: dict[str, float] | None = None,
    ) -> dict[str, QualityScore]:
        """Score all categories and compute weighted global score.

        Pondérations (somme = 1.00) :
          schools_score    20%  — accès à l'éducation
          transport_score  15%  — bus, vélo, mobilités douces
          transit_score    20%  — gares (effet TOD cloche)
          nuisances_score  20%  — nuisances inversées
          green_spaces     10%  — espaces verts
          commerce_score   15%  — commerces de proximité
        """
        if weights is None:
            weights = {
                "education":   0.20,
                "transport":   0.15,
                "transit":     0.20,
                "nuisances":   0.20,
                "environnement": 0.10,
                "commerce":    0.15,
            }

        scores = {}

        if "education" in proximities:
            scores["education"] = self.score_education(proximities["education"])

        if "transport" in proximities:
            scores["transport"] = self.score_transport(proximities["transport"])

        if "transit" in proximities:
            scores["transit"] = self.score_transit(proximities["transit"])

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
