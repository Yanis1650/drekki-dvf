"""Filiation service for parcel genealogy analysis.

Provides business logic for tracing parcel administrative history
using recursive graph algorithms with caching.
"""

import logging
from pathlib import Path

from app.domain.filiation_models import DFINature, FiliationNode
from app.repositories.filiation_repository import (
    DEFAULT_DEPTH_LIMIT,
    DuckDBFiliationRepository,
    IFiliationRepository,
)

logger = logging.getLogger(__name__)


class FiliationService:
    """Service for calculating parcel filiation trees.

    Delegates tree reconstruction to the repository (which enforces depth_limit
    and cycle detection). The service focuses on formatting and higher-level logic.

    Note : le LRU cache a été retiré de get_ancestors car la détection de cycles
    utilise un set mutable (_visited) incompatible avec functools.lru_cache.
    Le cache peut être réintroduit à un niveau supérieur (endpoint) si nécessaire.
    """

    def __init__(
        self,
        repository: IFiliationRepository | None = None,
        duckdb_path: Path | str = "./data/foncier.duckdb",
        depth_limit: int = DEFAULT_DEPTH_LIMIT,
    ) -> None:
        """Initialize filiation service.

        Args:
            repository:  Filiation repository (defaults to DuckDB)
            duckdb_path: Path to DuckDB database
            depth_limit: Maximum ancestor depth (default DEFAULT_DEPTH_LIMIT=10)
        """
        self._repo = repository or DuckDBFiliationRepository(db_path=duckdb_path)
        self._depth_limit = depth_limit

    def get_ancestors(
        self, code_commune: str, section: str, numero: str
    ) -> FiliationNode:
        """Retrieve ancestor tree with depth bounding and cycle detection.

        Delegates to repository.build_filiation_tree() which handles:
          - Depth limit (truncated=True when reached)
          - Cycle detection (truncated=True + ERROR logged when cycle found)
          - Optional geometry coherence validation (coherence_geo field)

        Args:
            code_commune: 3-digit commune code
            section:      2-char section
            numero:       4-char parcel number

        Returns:
            FiliationNode with parent chain; truncated=True on any node
            where the tree could not be fully reconstructed.
        """
        return self._repo.build_filiation_tree(
            code_commune,
            section,
            numero,
            depth_limit=self._depth_limit,
        )

    def format_filiation_summary(self, node: FiliationNode) -> str:
        """Format filiation for UI display.

        Examples:
        - "Issue de la parcelle AC0026 (divisée en 1990)"
        - "Issue de la parcelle BD1234 (lotie en 2015)"
        - "Parcelle originelle (pas de division connue)"

        Args:
            node: Filiation node to format

        Returns:
            Human-readable summary string
        """
        if not node.parent:
            return "Parcelle originelle (pas de division connue)"

        # Extract year from date
        year = node.date_division.year if node.date_division else "date inconnue"

        # Map operation type to French verb
        operation_map = {
            DFINature.ARPENTAGE: "divisée",
            DFINature.ARPENTAGE_NUMERIQUE: "divisée",
            DFINature.LOTISSEMENT: "lotie",
            DFINature.LOTISSEMENT_NUMERIQUE: "lotie",
            DFINature.REMANIEMENT: "remaniée",
            DFINature.RENOVATION: "rénovée",
            DFINature.CROQUIS_CONSERVATION: "modifiée",
        }

        operation = operation_map.get(node.nature_operation, "modifiée")

        return f"Issue de la parcelle {node.parent.id_parcelle} ({operation} en {year})"

    def get_filiation_chain(self, node: FiliationNode) -> list[dict]:
        """Extract linear ancestor chain from tree.

        Args:
            node: Root filiation node

        Returns:
            List of ancestors from oldest to newest
        """
        chain = []
        current = node

        while current.parent:
            chain.append(
                {
                    "id_parcelle": current.parent.id_parcelle,
                    "date_division": current.date_division,
                    "nature_operation": (
                        current.nature_operation.value
                        if current.nature_operation
                        else None
                    ),
                    "coherence_geo": current.coherence_geo,
                }
            )
            current = current.parent

        # Reverse to get oldest first
        return list(reversed(chain))

    def clear_cache(self) -> None:
        """No-op — LRU cache removed (cycle detection requires mutable state)."""
