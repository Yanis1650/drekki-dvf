"""Fonctions de decroissance : d'une distance vers un score 0-10.

Des courbes lisses plutot que des seuils durs, pour qu'un metre de plus ne
fasse pas basculer un score d'un cran entier.
"""

from math import exp


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

    @staticmethod
    def gaussian(
        distance: float,
        peak_distance: float = 600,
        sigma: float = 300,
    ) -> float:
        """Courbe en cloche (TOD — Transit-Oriented Development).

        Modélise l'effet non-monotone des gares :
          - Trop proche (< 200m) : bruit, score faible
          - Zone optimale 400-800m : score maximal ≈ 10
          - Au-delà de 1500m : effet quasi nul

        Formule : score = 10 * exp(-((d - peak_distance)² / (2 * sigma²)))
          peak_distance=600m, sigma=300m
          score ≈ 10.0 à 600m
          score ≈  6.1 à 300m et 900m
          score ≈  1.4 à 1200m (≈ 2*sigma de la crête)
          score ≈  1.4 à   0m  (même valeur qu'à 1200m par symétrie)
        """
        if distance is None or distance < 0:
            return 0.0
        return 10.0 * exp(-((distance - peak_distance) ** 2) / (2 * sigma ** 2))
