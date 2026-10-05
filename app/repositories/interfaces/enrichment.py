"""Acces aux scores d'enrichissement de proximite.

Contrat de depot. Aucune dependance a DuckDB : la couche metier ne connait
que ces signatures.
"""

from abc import ABC, abstractmethod

from app.domain.models import EnrichmentScore


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


# Profondeur max par défaut pour la reconstruction d'arbre.
# Les communes avec remembrements successifs peuvent dépasser 10 niveaux ;
# la troncature évite les timeouts et les récursions infinies sur cycles DFI.
