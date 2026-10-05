"""Contrats de depot, un module par contrat.

Le fichier unique depassait la limite de 200 lignes une fois la filiation
rapatriee depuis son implementation. Le decoupage suit celui, deja en place,
des mixins DuckDB : une responsabilite, un module.
"""

from .enrichment import IEnrichmentRepository
from .filiation import DEFAULT_DEPTH_LIMIT, IFiliationRepository
from .land import ILandRepository
from .transactions import ITransactionRepository

__all__ = [
    "DEFAULT_DEPTH_LIMIT",
    "IEnrichmentRepository",
    "IFiliationRepository",
    "ILandRepository",
    "ITransactionRepository",
]
