"""Infrastructure layer exports."""

from .data_availability import DataUnavailableError, require_table, table_exists
from .duckdb_pool import DuckDBPool, get_pool
from .duckdb_spatial import SpatialUnavailableError, ensure_spatial, require_spatial
from .osm_client import OsmClient, OsmPoiConfig, OsmTag

__all__ = [
    "DataUnavailableError",
    "DuckDBPool",
    "OsmClient",
    "OsmPoiConfig",
    "OsmTag",
    "SpatialUnavailableError",
    "ensure_spatial",
    "get_pool",
    "require_spatial",
    "require_table",
    "table_exists",
]
