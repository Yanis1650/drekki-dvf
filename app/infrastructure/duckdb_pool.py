"""DuckDB connection pool with LRU eviction per department.

Supports two modes:
  - Legacy: single foncier.duckdb (backward compatible)
  - Multi-dept: data/dept{XX}.duckdb with automatic routing

The department is extracted from id_parcelle[:2] or code_commune[:2].
Connections are read-only and cached with LRU eviction (default: 10 depts).
"""

import logging
import threading
from collections import OrderedDict
from pathlib import Path

import duckdb

from app.infrastructure.duckdb_spatial import ensure_spatial

logger = logging.getLogger(__name__)


class DuckDBPool:
    """Thread-safe LRU connection pool for per-department DuckDB files."""

    def __init__(
        self,
        data_dir: Path,
        legacy_path: Path | None = None,
        max_connections: int = 10,
    ):
        self._data_dir = Path(data_dir)
        self._legacy_path = Path(legacy_path) if legacy_path else None
        self._max = max_connections
        self._connections: OrderedDict[str, duckdb.DuckDBPyConnection] = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def extract_dept(identifier: str) -> str:
        """Extract department code from id_parcelle or code_commune.

        Handles Corsica (2A, 2B) and DOM (97X).
        """
        if not identifier or len(identifier) < 2:
            raise ValueError(f"Cannot extract dept from: {identifier!r}")
        prefix = identifier[:3]
        if prefix.startswith("97") and len(identifier) >= 3:
            return prefix[:3]
        if identifier[:2] in ("2A", "2B"):
            return identifier[:2]
        return identifier[:2]

    def _resolve_path(self, dept: str) -> Path:
        """Find the DB file for a department, falling back to legacy."""
        dept_path = self._data_dir / f"dept{dept}.duckdb"
        if dept_path.exists():
            return dept_path
        if self._legacy_path and self._legacy_path.exists():
            return self._legacy_path
        raise FileNotFoundError(
            f"Aucune base trouvee pour le dept {dept} "
            f"(cherche: {dept_path}, fallback: {self._legacy_path})"
        )

    def get_connection(self, dept: str) -> duckdb.DuckDBPyConnection:
        """Get or create a read-only connection for a department."""
        with self._lock:
            if dept in self._connections:
                self._connections.move_to_end(dept)
                return self._connections[dept]

            if len(self._connections) >= self._max:
                evict_key, evict_conn = self._connections.popitem(last=False)
                try:
                    evict_conn.close()
                except Exception as e:
                    logger.warning("Failed to close evicted DuckDB connection for %s: %s", evict_key, e)

            path = self._resolve_path(dept)
            conn = duckdb.connect(str(path), read_only=True)
            ensure_spatial(conn)
            self._connections[dept] = conn
            return conn

    def get_for_parcelle(self, id_parcelle: str) -> duckdb.DuckDBPyConnection:
        dept = self.extract_dept(id_parcelle)
        return self.get_connection(dept)

    def get_for_commune(self, code_commune: str) -> duckdb.DuckDBPyConnection:
        dept = self.extract_dept(code_commune)
        return self.get_connection(dept)

    @property
    def available_depts(self) -> list[str]:
        """List departments that have a dedicated DB file."""
        depts = []
        for p in sorted(self._data_dir.glob("dept*.duckdb")):
            code = p.stem.replace("dept", "")
            depts.append(code)
        return depts

    def close_all(self) -> None:
        """Close all cached connections."""
        with self._lock:
            for dept, conn in self._connections.items():
                try:
                    conn.close()
                except Exception as e:
                    logger.warning("Failed to close DuckDB connection for %s: %s", dept, e)
            self._connections.clear()


# ---------------------------------------------------------------------------
# Connexions partagees du mode base unique
#
# Repositories et services sont construits a chaque requete HTTP : les
# dependances FastAPI ne sont pas des generateurs, donc rien ne les referme.
# Chaque instance ouvrait donc sa propre connexion, rejouait `INSTALL spatial`
# et la laissait au ramasse-miettes. Ce registre aligne le mode base unique sur
# le mode multi-departements, ou le pool ci-dessus tient deja une connexion par
# departement pour toute la duree du processus.
#
# La base est ouverte en lecture seule, et le partage entre threads est
# exactement celui que le pool pratique deja.
# ---------------------------------------------------------------------------

_shared_lock = threading.Lock()
_shared_connections: dict[str, duckdb.DuckDBPyConnection] = {}


def _shared_key(db_path: Path | str) -> str:
    """Cle de registre : le chemin resolu, pour que deux graphies s'unifient."""
    return str(Path(db_path).resolve())


def get_shared_connection(db_path: Path | str) -> duckdb.DuckDBPyConnection:
    """Connexion partagee en lecture seule, une par fichier DuckDB."""
    key = _shared_key(db_path)
    with _shared_lock:
        conn = _shared_connections.get(key)
        if conn is None:
            conn = duckdb.connect(key, read_only=True)
            # Tentee une fois pour la connexion, jamais levee : les requetes
            # purement tabulaires restent servies si l'extension manque.
            ensure_spatial(conn)
            _shared_connections[key] = conn
        return conn


def close_shared_connection(db_path: Path | str) -> None:
    """Retire et ferme la connexion partagee d'un fichier, si elle existe.

    Aucun endpoint n'appelle `close()` sur un repository — la connexion vit
    autant que le processus. Cette fonction sert aux tests et aux scripts, qui
    ouvrent une base temporaire et doivent pouvoir la relacher.
    """
    key = _shared_key(db_path)
    with _shared_lock:
        conn = _shared_connections.pop(key, None)
    if conn is not None:
        try:
            conn.close()
        except Exception as e:
            logger.warning("Failed to close shared DuckDB connection for %s: %s", key, e)


def close_shared_connections() -> None:
    """Ferme toutes les connexions partagees. Appelee a l'arret de l'application."""
    with _shared_lock:
        connections = list(_shared_connections.items())
        _shared_connections.clear()
    for key, conn in connections:
        try:
            conn.close()
        except Exception as e:
            logger.warning("Failed to close shared DuckDB connection for %s: %s", key, e)


_pool: DuckDBPool | None = None


def get_pool(data_dir: str = "./data", legacy_path: str | None = None) -> DuckDBPool:
    """Get or create the global pool singleton."""
    global _pool
    if _pool is None:
        _pool = DuckDBPool(
            data_dir=Path(data_dir),
            legacy_path=Path(legacy_path) if legacy_path else Path(data_dir) / "foncier.duckdb",
            max_connections=10,
        )
    return _pool


def close_pool() -> None:
    """Ferme le pool s'il a ete cree. N'en cree jamais un pour le fermer."""
    global _pool
    if _pool is not None:
        _pool.close_all()
        _pool = None
