"""Tests Confidence Score — 3 corrections : double pénalité, DVF binaire, poids zone_non_mutable."""


from conftest import stub_missing_modules  # noqa: E402

stub_missing_modules(
    "geopandas", "fiona", "pyogrio", "shapely", "shapely.geometry",
    "shapely.validation", "shapely.ops", "shapely.strtree", "owslib", "owslib.wfs",
    "owslib.util", "pyproj", "pyproj.transformer", "requests", "osmnx", "networkx",
    "polars", "polars.exceptions", "polars.selectors", "aiohttp", "rtree",
)

import duckdb  # noqa: E402
import pytest  # noqa: E402
from etl_build_steps.confidence import step_confidence  # noqa: E402


def _setup(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("""
        CREATE TABLE densification_scores (
            id_parcelle VARCHAR, code_commune VARCHAR,
            source_ces VARCHAR, categorie VARCHAR, zone_non_mutable BOOLEAN
        )
    """)
    conn.execute("""
        CREATE TABLE france_foncier_test (
            cadastre_parcelle_id VARCHAR, date_mutation VARCHAR,
            dpe_energie VARCHAR, annee_construction INTEGER, hauteur_moyenne DOUBLE
        )
    """)


def _add_parcel(conn, id_p: str, source_ces: str, zone_non_mutable: bool = False) -> None:
    conn.execute(
        "INSERT INTO densification_scores VALUES (?, '35238', ?, 'MOYEN', ?)",
        [id_p, source_ces, zone_non_mutable],
    )


def _add_tx(conn, id_p: str, year: int = 2023, with_bdnb: bool = True) -> None:
    """Ajoute une transaction DVF, optionnellement avec données BDNB complètes (DPE+annee+hauteur)."""
    conn.execute(
        "INSERT INTO france_foncier_test VALUES (?, ?, ?, ?, ?)",
        [id_p, f"{year}-06-01",
         "D"   if with_bdnb else None,
         2000  if with_bdnb else None,
         10.0  if with_bdnb else None],
    )


@pytest.fixture()
def conn():
    c = duckdb.connect(":memory:")
    yield c
    c.close()


class TestDoublePenalite:
    """Problème 1 : rnu_proximite ne doit plus pénaliser BDNB et ZAN simultanément."""

    def test_rnu_sans_bdnb_penalite_unique_zan_010(self, conn):
        """rnu_proximite + aucune donnée BDNB → score_zan = 0.10 (pénalité unique consolidée)."""
        _setup(conn)
        _add_parcel(conn, "P1", "rnu_proximite")
        # Aucune ligne dans france_foncier_test → score_bdnb = 0.0

        step_confidence(conn, "35")

        row = conn.execute(
            "SELECT score_bdnb, score_zan FROM confidence_scores WHERE id_parcelle = 'P1'"
        ).fetchone()
        bdnb, zan = float(row[0]), float(row[1])
        assert bdnb == 0.0,  f"score_bdnb attendu 0.0, obtenu {bdnb}"
        assert zan == 0.10,  f"score_zan attendu 0.10 (pénalité unique), obtenu {zan}"

    def test_rnu_avec_bdnb_score_zan_030(self, conn):
        """rnu_proximite + BDNB complet → score_zan = 0.30 (emprise seule manquante)."""
        _setup(conn)
        _add_parcel(conn, "P2", "rnu_proximite")
        _add_tx(conn, "P2", year=2023, with_bdnb=True)

        step_confidence(conn, "35")

        row = conn.execute(
            "SELECT score_bdnb, score_zan FROM confidence_scores WHERE id_parcelle = 'P2'"
        ).fetchone()
        bdnb, zan = float(row[0]), float(row[1])
        assert bdnb == 1.0,  f"score_bdnb attendu 1.0 (DPE+annee+hauteur), obtenu {bdnb}"
        assert zan == 0.30,  f"score_zan attendu 0.30 (BDNB ok, emprise inconnue), obtenu {zan}"


class TestDVFBinaireZoneAgricole:
    """Problème 2 : DVF mesure la fiabilité, pas l'activité, pour les zones A/N."""

    def test_zone_non_mutable_score_dvf_est_fiabilite(self, conn):
        """Zone A/N + 1 tx → score_dvf = score_dvf_fiabilite = 1.0 (pas precision = 0.50)."""
        _setup(conn)
        _add_parcel(conn, "P3", "plu_gpu", zone_non_mutable=True)
        _add_tx(conn, "P3", year=2023)

        step_confidence(conn, "35")

        row = conn.execute(
            "SELECT score_dvf_fiabilite, score_dvf_precision, score_dvf "
            "FROM confidence_scores WHERE id_parcelle = 'P3'"
        ).fetchone()
        assert row[0] == 1.0,  "score_dvf_fiabilite doit être 1.0 avec 1 transaction"
        assert row[1] == 0.50, "score_dvf_precision doit être 0.50 avec 1 transaction"
        assert row[2] == 1.0,  "score_dvf zone_non_mutable doit utiliser score_dvf_fiabilite"

    def test_zone_mutable_score_dvf_est_precision(self, conn):
        """Zone U/AU + 1 tx → score_dvf = score_dvf_precision = 0.50."""
        _setup(conn)
        _add_parcel(conn, "P4", "plu_gpu", zone_non_mutable=False)
        _add_tx(conn, "P4", year=2023)

        step_confidence(conn, "35")

        row = conn.execute(
            "SELECT score_dvf FROM confidence_scores WHERE id_parcelle = 'P4'"
        ).fetchone()
        assert row[0] == 0.50, f"score_dvf zone mutable doit être score_dvf_precision, obtenu {row[0]}"


class TestPoidsZoneNonMutable:
    """Problème 3 : fraîcheur marché non pertinente pour zones A/N → poids redistribués."""

    def test_fraicheur_ignoree_formule_40_25_35(self, conn):
        """Zone A/N : fraîcheur = 0 exclue de la formule → conf = bdnb*0.40 + dvf_f*0.25 + zan*0.35."""
        _setup(conn)
        _add_parcel(conn, "P5", "plu_gpu", zone_non_mutable=True)
        # last_sale=2010 < 2014 → score_fraicheur = 0.0
        _add_tx(conn, "P5", year=2010, with_bdnb=True)

        step_confidence(conn, "35")

        row = conn.execute(
            "SELECT score_bdnb, score_dvf_fiabilite, score_zan, score_fraicheur, confidence_global "
            "FROM confidence_scores WHERE id_parcelle = 'P5'"
        ).fetchone()
        bdnb, dvf_f, zan, fraich, global_ = (float(x) for x in row)
        assert fraich == 0.0, f"score_fraicheur attendu 0.0 (vente 2010 < 2014), obtenu {fraich}"
        expected = round(bdnb * 0.40 + dvf_f * 0.25 + zan * 0.35, 2)
        assert abs(global_ - expected) < 0.01, (
            f"Formule zone_non_mutable (40/25/35) : attendu {expected}, obtenu {global_}"
        )

    def test_fraicheur_incluse_formule_30_25_25_20(self, conn):
        """Zone U/AU : formule standard 30/25/25/20 incluant fraîcheur récente."""
        _setup(conn)
        _add_parcel(conn, "P6", "plu_gpu", zone_non_mutable=False)
        _add_tx(conn, "P6", year=2023, with_bdnb=True)

        step_confidence(conn, "35")

        row = conn.execute(
            "SELECT score_bdnb, score_dvf_precision, score_zan, score_fraicheur, confidence_global "
            "FROM confidence_scores WHERE id_parcelle = 'P6'"
        ).fetchone()
        bdnb, dvf_p, zan, fraich, global_ = (float(x) for x in row)
        assert fraich == 1.0, f"score_fraicheur attendu 1.0 (vente 2023), obtenu {fraich}"
        expected = round(bdnb * 0.30 + dvf_p * 0.25 + zan * 0.25 + fraich * 0.20, 2)
        assert abs(global_ - expected) < 0.01, (
            f"Formule zone mutable (30/25/25/20) : attendu {expected}, obtenu {global_}"
        )
