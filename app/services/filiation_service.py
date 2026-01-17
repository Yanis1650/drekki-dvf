"""Filiation service for parcel genealogy analysis.

Provides business logic for tracing parcel administrative history
using recursive graph algorithms with caching.
"""

import logging
from functools import lru_cache
from pathlib import Path

from app.domain.filiation_models import DFINature, FiliationNode
from app.repositories.filiation_repository import (
    DuckDBFiliationRepository,
    IFiliationRepository,
)

logger = logging.getLogger(__name__)


class FiliationService:
    """Service for calculating parcel filiation trees.
    
    Uses recursive algorithms with LRU cache to efficiently trace
    parcel ancestors (administrative history).
    """

    MAX_DEPTH = 10  # Anti-infinite loop protection

    def __init__(
        self, repository: IFiliationRepository | None = None, duckdb_path: Path | str = "./data/foncier.duckdb"
    ) -> None:
        """Initialize filiation service.
        
        Args:
            repository: Filiation repository (defaults to DuckDB)
            duckdb_path: Path to DuckDB database
        """
        self._repo = repository or DuckDBFiliationRepository(db_path=duckdb_path)

    @lru_cache(maxsize=500)
    def get_ancestors(
        self, code_commune: str, section: str, numero: str, depth: int = 0
    ) -> FiliationNode:
        """Retrieve ancestor tree recursively with caching.
        
        Traces back the administrative history of a parcel by following
        mother-daughter relationships. Uses LRU cache to avoid redundant
        database queries.
        
        Args:
            code_commune: 3-digit commune code
            section: 2-char section
            numero: 4-char parcel number
            depth: Current recursion depth (internal)
            
        Returns:
            FiliationNode with parent chain
        """
        # Anti-infinite loop protection
        if depth >= self.MAX_DEPTH:
            logger.warning(
                f"Max depth {self.MAX_DEPTH} reached for {section}{numero} in commune {code_commune}"
            )
            return FiliationNode(
                id_parcelle=f"{section}{numero}",
                parent=None,
                children=[],
                depth=depth,
            )

        # Query direct parents
        parents = self._repo.get_parents(code_commune, section, numero)

        if not parents:
            # Leaf node (original parcel, no known division)
            return FiliationNode(
                id_parcelle=f"{section}{numero}",
                parent=None,
                children=[],
                depth=depth,
            )

        # Take first parent (most common case: simple division)
        # TODO: Handle multiple parents (fusion) in future version
        parent_filiation = parents[0]
        parent_section = parent_filiation.parcelle_mere[:2]
        parent_numero = parent_filiation.parcelle_mere[2:]

        # Recursive call to get parent's ancestors
        parent_node = self.get_ancestors(
            code_commune, parent_section, parent_numero, depth + 1
        )

        return FiliationNode(
            id_parcelle=f"{section}{numero}",
            parent=parent_node,
            children=[],
            date_division=parent_filiation.date_validation,
            nature_operation=parent_filiation.nature_dfi,
            depth=depth,
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
                    "nature_operation": current.nature_operation,
                }
            )
            current = current.parent

        # Reverse to get oldest first
        return list(reversed(chain))

    def clear_cache(self) -> None:
        """Clear LRU cache (useful for testing)."""
        self.get_ancestors.cache_clear()
