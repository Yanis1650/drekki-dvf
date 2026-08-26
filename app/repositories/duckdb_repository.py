"""DuckDB repository — composition des mixins.

Chaque mixin est dans app/repositories/duckdb/ et respecte la limite de 200 lignes.
"""


from app.repositories.duckdb import (
    DuckDBDensificationMixin,
    DuckDBEnrichmentMixin,
    DuckDBFicheMixin,
    DuckDBParcellesMixin,
    DuckDBTransactionsMixin,
    DuckDBTransactionsRadiusMixin,
)
from app.repositories.duckdb_base import DuckDBConnectionBase
from app.repositories.interfaces import (
    IEnrichmentRepository,
    ILandRepository,
    ITransactionRepository,
)


class DuckDBLandRepository(
    DuckDBConnectionBase,
    DuckDBParcellesMixin,
    DuckDBTransactionsMixin,
    DuckDBTransactionsRadiusMixin,
    DuckDBEnrichmentMixin,
    DuckDBFicheMixin,
    DuckDBDensificationMixin,
    ILandRepository,
    ITransactionRepository,
    IEnrichmentRepository,
):
    """DuckDB implementation of land repositories.

    Uses DuckDB's spatial extension for efficient local querying.
    Supports both legacy single-DB and multi-dept pool modes.
    """
