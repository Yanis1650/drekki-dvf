"""Tests détection outliers prix/m² — 4 cas : outlier flagué, normale incluse,
fallback département, is_outlier visible dans MutationAggregate (non filtré sur /fiche)."""

import sys
import types
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock


# Mocker les dépendances lourdes avant tout import du package ETL/app.
# MagicMock() avec __path__ : reconnu comme package ET gère tous les attributs
# dynamiquement (gpd.GeoDataFrame, pl.LazyFrame, etc.).
def _mock_pkg(name: str) -> MagicMock:
    m = MagicMock()
    m.__path__ = []
    m.__package__ = name
    m.__name__ = name
    return m


for _pkg in ("geopandas", "fiona", "pyogrio", "shapely", "owslib",
             "pyproj", "requests", "osmnx", "polars", "aiohttp"):
    if _pkg not in sys.modules:
        sys.modules[_pkg] = _mock_pkg(_pkg)

for _sub in (
    "polars.exceptions", "polars.selectors",
    "shapely.geometry", "shapely.validation", "shapely.ops",
    "owslib.wfs", "owslib.util",
    "pyproj.transformer",
):
    if _sub not in sys.modules:
        sys.modules[_sub] = MagicMock()

sys.path.insert(0, str(Path(__file__).parent.parent / "data-pipeline"))
from etl_build_steps.golden_join import _tag_outliers  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.domain.models import MutationAggregate, NatureMutation  # noqa: E402

import duckdb   # noqa: E402
import pytest   # noqa: E402


def _create_fft(conn: duckdb.DuckDBPyConnection) -> None:
    """Crée une france_foncier_test minimale (colonnes requises par _tag_outliers)."""
    conn.execute("""
        CREATE TABLE france_foncier_test (
            id_mutation  VARCHAR,
            date_mutation VARCHAR,
            code_commune VARCHAR,
            prix_m2      DOUBLE
        )
    """)


def _insert(conn, id_mutation: str, commune: str, prix_m2: float, year: int = 2022) -> None:
    conn.execute(
        "INSERT INTO france_foncier_test VALUES (?, ?, ?, ?)",
        [id_mutation, f"{year}-06-01", commune, prix_m2],
    )


@pytest.fixture()
def conn():
    c = duckdb.connect(":memory:")
    yield c
    c.close()


@pytest.fixture()
def conn_with_data(conn):
    """Données standard :
      - commune '35238' : 10 mutations à 3 000 €/m² + 1 outlier à 40 000 €/m²  (n=11 ≥ 10)
      - commune '35100' : 3 mutations à 3 000 €/m² + 1 outlier à 60 000 €/m²   (n=4 < 10)

    Valeurs distinctes pour les deux outliers : le dept P95 tombe entre elles (~46 000€/m²),
    ce qui permet de vérifier que M15 est détecté via le fallback départemental.
    """
    _create_fft(conn)
    for i in range(1, 11):
        _insert(conn, f"M{i:02d}", "35238", 3000.0)
    _insert(conn, "M11", "35238", 40000.0)   # outlier commune '35238' (n=11 ≥ 10)
    for i in range(12, 15):
        _insert(conn, f"M{i:02d}", "35100", 3000.0)
    _insert(conn, "M15", "35100", 60000.0)   # outlier commune '35100' (n=4 < 10, fallback dépt)
    return conn


class TestOutlierTag:
    def test_mutation_extreme_flagged_outlier(self, conn_with_data):
        """Prix 40 000€/m² dans commune ≥10 tx → is_outlier = True."""
        _tag_outliers(conn_with_data)
        row = conn_with_data.execute(
            "SELECT is_outlier FROM france_foncier_test WHERE id_mutation = 'M11'"
        ).fetchone()
        assert row[0] is True, "40 000€/m² doit être flagué outlier"

    def test_mutation_normale_non_flagee(self, conn_with_data):
        """Prix 3 000€/m² dans commune ≥10 tx → is_outlier = False."""
        _tag_outliers(conn_with_data)
        row = conn_with_data.execute(
            "SELECT is_outlier FROM france_foncier_test WHERE id_mutation = 'M01'"
        ).fetchone()
        assert row[0] is False, "3 000€/m² normal ne doit pas être flagué outlier"

    def test_outlier_exclu_avg_prix_m2_commune(self, conn_with_data):
        """AVG(prix_m2) sans outliers = 3 000 — l'outlier 50 000€/m² est exclu."""
        _tag_outliers(conn_with_data)
        avg = conn_with_data.execute("""
            SELECT AVG(prix_m2) FROM france_foncier_test
            WHERE code_commune = '35238' AND NOT is_outlier
        """).fetchone()[0]
        assert abs(float(avg) - 3000.0) < 0.01, (
            f"AVG sans outliers attendu 3000.0, obtenu {avg}"
        )


class TestFallbackDept:
    def test_petite_commune_outlier_detecte_via_dept(self, conn_with_data):
        """Commune avec n=4 < 10 tx → fallback dépt → outlier 50 000€/m² détecté."""
        _tag_outliers(conn_with_data)
        # Vérifie que la commune a bien < 10 transactions (fallback actif)
        n = conn_with_data.execute(
            "SELECT COUNT(*) FROM france_foncier_test WHERE code_commune = '35100'"
        ).fetchone()[0]
        assert n == 4, f"La commune '35100' doit avoir 4 transactions, trouvé {n}"

        row = conn_with_data.execute(
            "SELECT is_outlier FROM france_foncier_test WHERE id_mutation = 'M15'"
        ).fetchone()
        assert row[0] is True, (
            "Outlier 50 000€/m² dans petite commune (fallback dépt) doit être flagué"
        )

    def test_petite_commune_normale_non_flaguee(self, conn_with_data):
        """Transaction normale dans petite commune (fallback dépt) → is_outlier = False."""
        _tag_outliers(conn_with_data)
        row = conn_with_data.execute(
            "SELECT is_outlier FROM france_foncier_test WHERE id_mutation = 'M12'"
        ).fetchone()
        assert row[0] is False, (
            "3 000€/m² dans petite commune (fallback dépt) ne doit pas être flagué"
        )


class TestTransactionDetailSchema:
    def test_is_outlier_expose_dans_mutation_aggregate(self):
        """MutationAggregate.is_outlier = True est retourné sans filtre (vue /fiche)."""
        m = MutationAggregate(
            id_mutation="test_outlier",
            date_mutation=date(2023, 6, 1),
            nature_mutation=NatureMutation.VENTE,
            valeur_fonciere=Decimal("5000000"),
            code_commune="35238",
            parcelles=["35238000AB0001"],
            surface_habitable_totale=Decimal("100"),
            nombre_locaux=1,
            is_outlier=True,
        )
        assert m.is_outlier is True, "is_outlier=True doit être exposé dans le schéma"

    def test_is_outlier_default_false(self):
        """is_outlier = False par défaut — rétrocompatibilité avec transactions sans flag."""
        m = MutationAggregate(
            id_mutation="test_normal",
            date_mutation=date(2023, 6, 1),
            nature_mutation=NatureMutation.VENTE,
            valeur_fonciere=Decimal("200000"),
            code_commune="35238",
            parcelles=["35238000AB0001"],
            surface_habitable_totale=Decimal("80"),
            nombre_locaux=1,
        )
        assert m.is_outlier is False, "is_outlier doit être False par défaut"
