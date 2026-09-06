"""Acces au parcellaire.

Contrat de depot. Aucune dependance a DuckDB : la couche metier ne connait
que ces signatures.
"""

from abc import ABC, abstractmethod

from app.domain.models import Parcelle


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
