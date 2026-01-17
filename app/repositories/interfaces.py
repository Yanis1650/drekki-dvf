"""Repository interfaces (ABCs).

Defines contracts for data access, following Interface Segregation Principle.
"""

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal

from app.domain.models import EnrichmentScore, MutationAggregate, Parcelle, Transaction


class ILandRepository(ABC):
    """Interface for land/parcel data access."""

    @abstractmethod
    async def get_parcelle_by_id(self, id_parcelle: str) -> Parcelle | None:
        """Retrieve a single parcel by its ID."""
        ...

    @abstractmethod
    async def get_parcelles_by_commune(self, code_commune: str) -> list[Parcelle]:
        """Retrieve all parcels in a commune."""
        ...

    @abstractmethod
    async def get_parcelles_in_bbox(
        self,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
    ) -> list[Parcelle]:
        """Retrieve parcels within a bounding box (Lambert-93)."""
        ...


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


class IEnrichmentRepository(ABC):
    """Interface for qualitative enrichment data access."""

    @abstractmethod
    async def get_enrichment_by_parcelle(self, id_parcelle: str) -> EnrichmentScore | None:
        """Retrieve enrichment score for a parcel."""
        ...

    @abstractmethod
    async def get_enrichments_by_commune(self, code_commune: str) -> list[EnrichmentScore]:
        """Retrieve all enrichment scores for a commune."""
        ...
