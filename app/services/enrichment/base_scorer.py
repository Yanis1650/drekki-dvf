"""Base scorer interface (Strategy Pattern).

Defines the contract for all scoring strategies.
"""

from abc import ABC, abstractmethod
from decimal import Decimal


class IScorer(ABC):
    """Interface for POI-based scoring strategies.

    Each scorer calculates a score from 0 to 10 based on
    proximity to specific types of POI.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Scorer identifier name."""
        ...

    @property
    @abstractmethod
    def poi_type(self) -> str:
        """Type of POI this scorer evaluates."""
        ...

    @abstractmethod
    async def calculate_score(
        self,
        latitude: float,
        longitude: float,
    ) -> Decimal:
        """Calculate score for a given location.

        Args:
            latitude: WGS84 latitude
            longitude: WGS84 longitude

        Returns:
            Score from 0 (worst) to 10 (best)
        """
        ...

    @abstractmethod
    async def calculate_score_with_details(
        self,
        latitude: float,
        longitude: float,
    ) -> dict:
        """Calculate score with detailed breakdown.

        Args:
            latitude: WGS84 latitude
            longitude: WGS84 longitude

        Returns:
            Dict with score and details (nearby POI count, distances, etc.)
        """
        ...
