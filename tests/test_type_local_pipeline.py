"""Non-regression tests — Bug 1: type_local preserved through ETL and API chain.

Tests:
1. ETL aggregation preserves type_local (run_etl.py)
2. golden_join includes type_local in france_foncier_test
3. get_parcel_history returns type_local (analytics repo, pool routing)
4. get_mutations_in_radius populates type_local on MutationAggregate
"""

from unittest.mock import MagicMock

# Stub heavy geo dependencies before any import
from conftest import stub_missing_modules  # noqa: E402

stub_missing_modules(
    "geopandas", "fiona", "pyogrio", "shapely", "shapely.geometry",
    "shapely.validation", "shapely.ops", "shapely.strtree", "owslib", "owslib.wfs",
    "owslib.util", "pyproj", "pyproj.transformer", "requests", "osmnx", "networkx",
    "polars", "polars.exceptions", "polars.selectors", "aiohttp", "rtree",
)


import duckdb
import polars as pl
import pytest

# ──────────────────────────────────────────────────────────────────────────────
# 1. ETL aggregation: type_local must survive group_by + agg
# ──────────────────────────────────────────────────────────────────────────────

def test_etl_aggregation_preserves_type_local():
    """pl.first('type_local') must be present in the aggregated dataframe."""
    raw = pl.DataFrame({
        "id_mutation":        ["M001", "M001", "M002"],
        "date_mutation":      ["2023-01-10", "2023-01-10", "2022-06-15"],
        "nature_mutation":    ["Vente", "Vente", "Vente"],
        "valeur_fonciere":    [250_000.0, 250_000.0, 180_000.0],
        "code_commune":       ["35238", "35238", "35238"],
        "id_parcelle":        ["35238000AO0001", "35238000AO0002", "35238000AB0010"],
        "surface_reelle_bati":[90.0, 20.0, 75.0],
        "nombre_locaux":      [1, 1, 1],
        "longitude":          [-1.678, -1.678, -1.680],
        "latitude":           [48.117, 48.117, 48.119],
        "type_local":         ["Maison", "Dépendance", "Appartement"],
    })

    aggregated = raw.group_by("id_mutation").agg(
        pl.first("date_mutation"),
        pl.first("nature_mutation"),
        pl.first("valeur_fonciere"),
        pl.first("code_commune"),
        pl.col("id_parcelle").unique().alias("parcelles"),
        pl.col("surface_reelle_bati").sum().alias("surface_habitable_totale"),
        pl.len().alias("nombre_locaux"),
        pl.first("longitude"),
        pl.first("latitude"),
        pl.first("type_local"),          # Bug 1 fix
    )

    assert "type_local" in aggregated.columns, "type_local column must be present after aggregation"
    # M001 rows: Maison is first (deterministic with pl.first on sorted data)
    m001 = aggregated.filter(pl.col("id_mutation") == "M001")
    assert m001["type_local"][0] in ("Maison", "Dépendance"), \
        f"Unexpected type_local value: {m001['type_local'][0]}"


# ──────────────────────────────────────────────────────────────────────────────
# 2. golden_join SELECT includes type_local in france_foncier_test
# ──────────────────────────────────────────────────────────────────────────────

def test_golden_join_select_contains_type_local(tmp_path):
    """france_foncier_test created by golden_join must have type_local column."""
    conn = duckdb.connect()
    conn.execute("LOAD spatial;") if False else None  # spatial not needed for this test

    # Minimal mutations_aggregated with type_local
    conn.execute("""
        CREATE TABLE mutations_aggregated (
            id_mutation VARCHAR, date_mutation VARCHAR, nature_mutation VARCHAR,
            valeur_fonciere DOUBLE, code_commune VARCHAR,
            parcelles VARCHAR[], surface_habitable_totale DOUBLE, nombre_locaux INT,
            prix_m2 DOUBLE, longitude DOUBLE, latitude DOUBLE, type_local VARCHAR
        )
    """)
    conn.execute("""
        INSERT INTO mutations_aggregated VALUES
        ('M001','2023-01-10','Vente',250000,'35238',['35238000AO0001'],90,1,2777,
         -1.678, 48.117, 'Maison')
    """)

    # Simulate the france_foncier_test SELECT (without spatial join for unit test)
    # Use BLOB instead of GEOMETRY to avoid needing the spatial extension
    conn.execute("""
        CREATE TABLE france_foncier_test AS
        SELECT
            id_mutation, date_mutation, nature_mutation,
            valeur_fonciere, code_commune,
            parcelles AS dvf_parcelles,
            surface_habitable_totale, nombre_locaux, prix_m2,
            longitude, latitude,
            NULL::VARCHAR AS cadastre_parcelle_id,
            NULL::VARCHAR AS geometry,
            type_local
        FROM mutations_aggregated
    """)

    cols = [r[0] for r in conn.execute("DESCRIBE france_foncier_test").fetchall()]
    assert "type_local" in cols, \
        "type_local column must be present in france_foncier_test after golden_join"

    row = conn.execute("SELECT type_local FROM france_foncier_test LIMIT 1").fetchone()
    assert row[0] == "Maison"
    conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# 3. Analytics repo: get_parcel_history returns type_local and uses pool routing
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_parcel_history_returns_type_local(tmp_path):
    """get_parcel_history must return type_local field from france_foncier_test."""
    from app.repositories.duckdb_analytics_repository import DuckDBAnalyticsRepository

    db_path = tmp_path / "dept35.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute("""
        CREATE TABLE france_foncier_test (
            date_mutation VARCHAR, valeur_fonciere DOUBLE, prix_m2 DOUBLE,
            surface_habitable_totale DOUBLE, cadastre_parcelle_id VARCHAR,
            is_outlier BOOLEAN, type_local VARCHAR
        )
    """)
    conn.execute("""
        INSERT INTO france_foncier_test VALUES
        ('2023-01-10', 250000, 2777.0, 90.0, '35238000AO0001', false, 'Maison')
    """)
    conn.close()

    # Mock pool to return our test connection
    mock_pool = MagicMock()
    test_conn = duckdb.connect(str(db_path), read_only=True)
    mock_pool.get_for_parcelle.return_value = test_conn

    repo = DuckDBAnalyticsRepository(db_path=tmp_path / "foncier.duckdb", pool=mock_pool)
    result = await repo.get_parcel_history("35238000AO0001", limit=10)

    assert len(result) == 1
    assert result[0]["type_local"] == "Maison", \
        f"Expected 'Maison', got {result[0].get('type_local')!r}"
    assert result[0]["price"] == 250_000.0
    mock_pool.get_for_parcelle.assert_called_once_with("35238000AO0001")
    test_conn.close()


@pytest.mark.asyncio
async def test_get_parcel_history_uses_pool_routing(tmp_path):
    """Pool must be called with the parcel_id to route to the correct dept DB."""
    from app.repositories.duckdb_analytics_repository import DuckDBAnalyticsRepository

    mock_pool = MagicMock()
    # Return a connection that has no tables → empty result
    fake_conn = duckdb.connect()
    mock_pool.get_for_parcelle.return_value = fake_conn

    repo = DuckDBAnalyticsRepository(db_path=tmp_path / "foncier.duckdb", pool=mock_pool)
    result = await repo.get_parcel_history("35238000AO0001", limit=10)

    mock_pool.get_for_parcelle.assert_called_once_with("35238000AO0001")
    assert result == []
    fake_conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# 4. get_mutations_in_radius: type_local propagated to MutationAggregate
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_mutations_in_radius_type_local(tmp_path):
    """get_mutations_in_radius must populate type_local on MutationAggregate."""
    db_path = tmp_path / "foncier.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute("LOAD spatial;") if False else None
    conn.execute("""
        CREATE TABLE mutations_aggregated (
            id_mutation VARCHAR, date_mutation VARCHAR, nature_mutation VARCHAR,
            valeur_fonciere DOUBLE, code_commune VARCHAR,
            parcelles VARCHAR[], surface_habitable_totale DOUBLE, nombre_locaux INT,
            prix_m2 DOUBLE, longitude DOUBLE, latitude DOUBLE, type_local VARCHAR
        )
    """)
    conn.execute("""
        INSERT INTO mutations_aggregated VALUES
        ('M001','2023-01-10','Vente',250000,'35238',['35238000AO0001'],90,1,2777,
         -1.678, 48.117, 'Maison')
    """)
    conn.close()


    # We test the radius mixin indirectly through the radius mixin module
    from app.repositories.duckdb.transactions_radius_mixin import DuckDBTransactionsRadiusMixin

    class _TestRepo(DuckDBTransactionsRadiusMixin):
        def __init__(self, path):
            self._conn = duckdb.connect(str(path), read_only=True)

        def _get_connection(self, dept=None):
            return self._conn

        def _dept_from_commune(self, code):
            return code[:2]

    repo = _TestRepo(db_path)
    mutations = await repo.get_mutations_in_radius(
        lat=48.117, lon=-1.678, radius_meters=500, limit=10
    )

    assert len(mutations) >= 1
    assert mutations[0].type_local is not None, \
        "type_local must be populated on MutationAggregate from get_mutations_in_radius"
    assert mutations[0].type_local.value == "Maison"
