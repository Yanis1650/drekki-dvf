"""Acces aux mutations DVF.

Contrat de depot. Aucune dependance a DuckDB : la couche metier ne connait
que ces signatures.
"""

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal

from app.domain.models import MutationAggregate, Transaction


class ITransactionRepository(ABC):
    """Interface for DVF transaction data access."""

    @abstractmethod
    async def get_transactions_by_commune(
        self,
        code_commune: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[Transaction]:
        """Retrieve transactions for a commune with optional date filter."""
        ...

    @abstractmethod
    async def get_mutations_by_commune(
        self,
        code_commune: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[MutationAggregate]:
        """Retrieve aggregated mutations for a commune."""
        ...

    @abstractmethod
    async def get_transactions_in_bbox(
        self,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[Transaction]:
        """Retrieve transactions within a bounding box."""
        ...

    @abstractmethod
    async def get_price_stats(
        self,
        code_commune: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, Decimal]:
        """Get price statistics (min, max, median, avg) for a commune."""
        ...

    @abstractmethod
    async def get_mutations_in_radius(
        self,
        lat: float,
        lon: float,
        radius_meters: int,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 100,
    ) -> list[MutationAggregate]:
        """Retrieve mutations within a radius of a point (WGS84).

        Uses Haversine formula for accurate distance calculation.

        Args:
            lat: Latitude WGS84
            lon: Longitude WGS84
            radius_meters: Search radius in meters
            date_from: Optional start date filter
            date_to: Optional end date filter
            limit: Maximum number of results

        Returns:
            List of mutations within the radius, ordered by distance
        """
        ...
