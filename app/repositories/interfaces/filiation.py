"""Acces a la filiation cadastrale.

Contrat de depot. Aucune dependance a DuckDB : la couche metier ne connait
que ces signatures.
"""

from abc import ABC, abstractmethod

from app.domain.filiation_models import FiliationNode, ParcelFiliation

DEFAULT_DEPTH_LIMIT = 10


class IFiliationRepository(ABC):
    """Interface for parcel filiation data access."""

    @abstractmethod
    def get_parents(
        self, code_commune: str, section: str, numero: str
    ) -> list[ParcelFiliation]:
        """Retrieve direct parent parcels (mothers).

        Args:
            code_commune: 3-digit commune code (ex: "001")
            section: 2-char section (ex: "AC")
            numero: 4-char parcel number (ex: "0214")

        Returns:
            List of parent filiations (may be empty)
        """

    @abstractmethod
    def get_children(
        self, code_commune: str, section: str, numero: str
    ) -> list[ParcelFiliation]:
        """Retrieve direct children parcels (daughters).

        Args:
            code_commune: 3-digit commune code
            section: 2-char section
            numero: 4-char parcel number

        Returns:
            List of children filiations (may be empty)
        """

    @abstractmethod
    def build_filiation_tree(
        self,
        code_commune: str,
        section: str,
        numero: str,
        depth_limit: int = DEFAULT_DEPTH_LIMIT,
        _depth: int = 0,
        _visited: set[str] | None = None,
    ) -> FiliationNode:
        """Reconstruct the ancestor tree with depth bounding and cycle detection.

        Args:
            code_commune: 3-digit commune code
            section: 2-char section
            numero: 4-char parcel number
            depth_limit: Maximum recursion depth before truncation (default 10)
            _depth: Current depth (internal — do not pass from outside)
            _visited: Set of already-visited parcelle IDs (internal — cycle detection)

        Returns:
            FiliationNode with parent chain, possibly truncated.
        """

    @abstractmethod
    def calculate_coherence_geo(
        self,
        id_mere: str,
        id_fille: str,
    ) -> str:
        """Compute geometric coherence between a mother and daughter parcel.

        Uses ST_Intersection to compute area_overlap_pct =
          ST_Area(ST_Intersection(mere, fille)) / ST_Area(fille)

        Returns:
            'OK'             if overlap_pct >= 0.80
            'PARTIELLE'      if overlap_pct >= 0.30
            'DOUTEUSE'       if overlap_pct <  0.30  (WARNING logged)
            'NON_VERIFIABLE' if geometries not available or query fails
        """
