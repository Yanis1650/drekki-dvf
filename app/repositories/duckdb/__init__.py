"""DuckDB repository package — mixins composés dans DuckDBLandRepository."""

from app.repositories.duckdb.parcelles_mixin import DuckDBParcellesMixin
from app.repositories.duckdb.transactions_mixin import DuckDBTransactionsMixin
from app.repositories.duckdb.transactions_radius_mixin import DuckDBTransactionsRadiusMixin
from app.repositories.duckdb.enrichment_mixin import DuckDBEnrichmentMixin
from app.repositories.duckdb.fiche_mixin import DuckDBFicheMixin
from app.repositories.duckdb.densification_mixin import DuckDBDensificationMixin

__all__ = [
    "DuckDBParcellesMixin",
    "DuckDBTransactionsMixin",
    "DuckDBTransactionsRadiusMixin",
    "DuckDBEnrichmentMixin",
    "DuckDBFicheMixin",
    "DuckDBDensificationMixin",
]
