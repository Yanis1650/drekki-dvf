"""Pytest fixtures shared across tests."""

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock

import duckdb
import pytest

# Les modules ETL vivent hors du package `app`.
DATA_PIPELINE = Path(__file__).parent.parent / "data-pipeline"
if str(DATA_PIPELINE) not in sys.path:
    sys.path.insert(0, str(DATA_PIPELINE))


def _make_stub(name: str) -> MagicMock:
    """Faux module utilisable comme package (import de sous-modules autorisé)."""
    stub = MagicMock()
    stub.__path__ = []
    stub.__package__ = name
    stub.__name__ = name
    return stub


def stub_missing_modules(*names: str) -> list[str]:
    """Bouchonne les dépendances lourdes *réellement absentes* de l'environnement.

    Les modules ETL importent geopandas, shapely, osmnx… que l'on ne veut pas
    exiger pour des tests unitaires. Mais bouchonner sans condition casse tout :
    poser un MagicMock sur `shapely` alors que shapely est installé fait ensuite
    échouer `from shapely.strtree import STRtree` chez osmnx avec
    « 'shapely' is not a package » — et comme `sys.modules` est global au
    processus, la casse frappe les fichiers de test suivants, pas celui qui l'a
    provoquée. C'est ce qui rendait la suite verte fichier par fichier et rouge
    en exécution complète.

    On ne bouchonne donc que ce qui ne s'importe pas.

    Returns:
        Les noms effectivement bouchonnés.
    """
    stubbed = []
    for name in names:
        if name in sys.modules:
            continue
        try:
            importlib.import_module(name)
        except Exception:
            sys.modules[name] = _make_stub(name)
            stubbed.append(name)
    return stubbed


def spatial_available() -> bool:
    """Indique si l'extension spatiale DuckDB peut être chargée ici.

    Elle est téléchargée puis chargée dynamiquement : réseau absent ou
    stratégie de contrôle d'application (Smart App Control / WDAC sous Windows)
    suffisent à la rendre indisponible, sans que le code testé soit en cause.
    """
    try:
        conn = duckdb.connect(":memory:")
        conn.execute("INSTALL spatial; LOAD spatial;")
        conn.close()
        return True
    except Exception:
        return False


SPATIAL_AVAILABLE = spatial_available()

requires_spatial = pytest.mark.skipif(
    not SPATIAL_AVAILABLE,
    reason="extension DuckDB spatial indisponible dans cet environnement",
)


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Temporary data directory for ETL/DB tests."""
    data = tmp_path / "data"
    data.mkdir()
    return data


@pytest.fixture
def duckdb_conn_inmemory():
    """In-memory DuckDB connection with spatial extension."""
    if not SPATIAL_AVAILABLE:
        pytest.skip("extension DuckDB spatial indisponible dans cet environnement")
    conn = duckdb.connect(":memory:")
    conn.execute("INSTALL spatial; LOAD spatial;")
    yield conn
    conn.close()


@pytest.fixture
def duckdb_conn_plain():
    """In-memory DuckDB connection sans extension spatiale.

    Pour les tests purement tabulaires, qui doivent tourner partout.
    """
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def duckdb_conn_with_fixtures(duckdb_conn_inmemory):
    """DuckDB connection with france_foncier_test and parcelles for GeoJSON tests.

    Uses code_commune 35xxx (Rennes) to match the dept_prefix used in tests.
    """
    conn = duckdb_conn_inmemory
    # `is_outlier` fait partie du schema reel (migration add_outlier_flag.sql) :
    # l'omettre ici masquait le fait que la requete GeoJSON en depend.
    conn.execute("""
        CREATE TABLE france_foncier_test (
            id_mutation VARCHAR,
            longitude DOUBLE,
            latitude DOUBLE,
            prix_m2 DOUBLE,
            date_mutation DATE,
            valeur_fonciere DOUBLE,
            nature_mutation VARCHAR,
            is_outlier BOOLEAN
        )
    """)
    conn.execute("""
        INSERT INTO france_foncier_test VALUES
        ('MUT001', -1.68, 48.11, 2500.0, '2024-01-15', 150000.0, 'Vente', FALSE),
        ('MUT002', -1.69, 48.12, 3000.0, '2023-06-20', 200000.0, 'Vente', TRUE)
    """)
    conn.execute("""
        CREATE TABLE parcelles (
            code_commune VARCHAR,
            prefixe VARCHAR,
            section VARCHAR,
            numero VARCHAR,
            geometry GEOMETRY
        )
    """)
    # Lambert-93 (EPSG:2154) autour de Rennes : (352107, 6789966) ~ (-1.6778, 48.1173).
    # L'ancienne fixture utilisait (515000, 6800000), qui tombe pres d'Orleans —
    # hors de toute bbox « dept 35 » testee. DuckDB spatial stocke la geometrie
    # sans SRID : ST_GeomFromText ne prend pas de second argument entier.
    conn.execute("""
        INSERT INTO parcelles VALUES
        ('35238', '000', 'AB', '0297',
         ST_GeomFromText('POLYGON((352100 6789900, 352190 6789900, 352190 6790000, 352100 6790000, 352100 6789900))'))
    """)
    yield conn


@pytest.fixture
def duckdb_conn_densification(duckdb_conn_inmemory):
    """DuckDB connection with densification_scores for utils.print_distribution."""
    conn = duckdb_conn_inmemory
    conn.execute("""
        CREATE TABLE densification_scores (
            id_parcelle VARCHAR,
            code_commune VARCHAR,
            categorie VARCHAR,
            surface_parcelle_m2 DOUBLE
        )
    """)
    conn.execute("""
        INSERT INTO densification_scores VALUES
        ('35238000AB0297', '35238', 'FORT', 1000),
        ('35238000AB0298', '35238', 'MOYEN', 800),
        ('35238000AB0299', '35238', 'FAIBLE', 500),
        ('35238000AB0300', '35238', 'SATURE', 600)
    """)
    yield conn
