"""Les deux scores qui rompent la monotonie de la distance.

Le transit a un optimum : une gare a 600 m vaut mieux qu'une gare sous les
fenetres. Les nuisances s'inversent : la proximite y est une penalite. Les
isoler ici evite qu'on les traite par distraction comme les quatre autres.
"""

from decimal import Decimal

from app.services.enrichment.proximity_scorer import ProximityResult
from app.services.enrichment.scoring.models import QualityScore


class TransitNuisanceScoresMixin:
    """Scores non monotones : optimum intermediaire, ou penalite inversee."""

    def score_transit(self, proximity: ProximityResult) -> QualityScore:
        """Score TOD (Transit-Oriented Development) — effet cloche gaussien.

        La proximité d'une gare est un facteur POSITIF avec un optimum à 600m :
          - Trop loin (> 1500m) : peu d'effet
          - Zone optimale (400-800m) : score ≈ 10
          - Trop proche (< 200m) : bruit fort, score bas (≈ 1-2)

        Utilise DecayFunction.gaussian() — pas exponentielle, pas linéaire.
        Contrairement au transport_score (bus/vélo), aucun bonus de comptage :
        la présence d'une seule grande gare suffit.
        """
        raw = self._decay.gaussian(
            proximity.nearest_distance_m,
            peak_distance=self.TRANSIT_PEAK,
            sigma=self.TRANSIT_SIGMA,
        )
        total = min(10.0, raw)

        return QualityScore(
            category="transit",
            score=Decimal(str(round(total, 1))),
            details={
                "raw_gaussian": round(raw, 3),
                "nearest_m": proximity.nearest_distance_m,
                "count_1km": proximity.count_1km,
                "types": proximity.poi_types,
                "peak_distance_m": self.TRANSIT_PEAK,
                "sigma_m": self.TRANSIT_SIGMA,
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
