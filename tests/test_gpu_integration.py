"""Tests d'intégration GPU : 1.Zone U  2.PLUi SIREN  3.Fallback sans PLU  4.Sous-zones  5.Partition sans zones."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Stub les dépendances ETL lourdes (geopandas/fiona/shapely) absentes du venv de test.
for _m in ("geopandas", "fiona", "shapely", "shapely.geometry", "shapely.validation"):
    sys.modules.setdefault(_m, MagicMock())

sys.path.insert(0, str(Path(__file__).parent.parent / "data-pipeline"))
from etl_build_steps.gpu import step_gpu  # noqa: E402

import duckdb  # noqa: E402
import pytest  # noqa: E402


def _wkt_box(cx: float, cy: float, half: float = 1_000.0) -> str:
    x0, y0, x1, y1 = cx - half, cy - half, cx + half, cy + half
    return f"POLYGON(({x0} {y0},{x1} {y0},{x1} {y1},{x0} {y1},{x0} {y0}))"


def _create_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("""
        CREATE TABLE parcelles (
            id_parcelle VARCHAR, code_commune VARCHAR,
            section VARCHAR, numero VARCHAR, geometry GEOMETRY
        )
    """)
    conn.execute("""
        CREATE TABLE densification_scores (
            id_parcelle VARCHAR, code_commune VARCHAR,
            surface_parcelle_m2 DOUBLE, surface_plancher_m2 DOUBLE,
            emprise_sol_m2 DOUBLE, ces_actuel DOUBLE, ces_potentiel DOUBLE,
            potentiel_densification DOUBLE, surface_constructible_restante DOUBLE,
            source_ces VARCHAR, type_usage VARCHAR, nb_niveau INTEGER, categorie VARCHAR
        )
    """)


def _add_parcelle(conn, id_p: str, commune: str,
                  cx: float = 515_000.0, cy: float = 6_800_000.0) -> None:
    conn.execute(
        "INSERT INTO parcelles VALUES (?, ?, 'AB', '0001', ST_GeomFromText(?))",
        [id_p, commune, _wkt_box(cx, cy, half=500.0)],
    )
    conn.execute(
        "INSERT INTO densification_scores VALUES "
        "(?, ?, 250000, 0, NULL, NULL, 0.40, NULL, NULL, 'inconnu', NULL, NULL, 'INCONNU')",
        [id_p, commune],
    )


def _add_plu(conn, commune: str, partition: str, typezone: str,
             cx: float = 515_000.0, cy: float = 6_800_000.0) -> None:
    conn.execute("DROP TABLE IF EXISTS plu_commune_partition")
    conn.execute("DROP TABLE IF EXISTS plu_zones")
    conn.execute("CREATE TABLE plu_commune_partition (code_commune VARCHAR, partition VARCHAR)")
    conn.execute("INSERT INTO plu_commune_partition VALUES (?, ?)", [commune, partition])
    conn.execute("CREATE INDEX idx_pcp ON plu_commune_partition(code_commune)")
    conn.execute("CREATE TABLE plu_zones "
                 "(partition VARCHAR, typezone VARCHAR, libelle VARCHAR, datappro DATE, geometry GEOMETRY)")
    conn.execute(
        "INSERT INTO plu_zones VALUES (?, ?, 'Zone test', '2022-06-01', ST_GeomFromText(?))",
        [partition, typezone, _wkt_box(cx, cy, half=5_000.0)],
    )


def _empty_plu(conn, map_commune: bool = False) -> None:
    """PLU tables vides. Si map_commune=True, le mapping commune→partition existe mais plu_zones est vide.

    map_commune=False → motif 'no_plu_gpu' (commune absente de plu_commune_partition)
    map_commune=True  → motif 'partition_without_zones' (partition mappée, aucune zone)
    """
    conn.execute("DROP TABLE IF EXISTS plu_commune_partition")
    conn.execute("DROP TABLE IF EXISTS plu_zones")
    conn.execute("CREATE TABLE plu_commune_partition (code_commune VARCHAR, partition VARCHAR)")
    if map_commune:
        conn.execute("INSERT INTO plu_commune_partition VALUES ('35238', 'DU_35238')")
    conn.execute("CREATE TABLE plu_zones "
                 "(partition VARCHAR, typezone VARCHAR, libelle VARCHAR, datappro DATE, geometry GEOMETRY)")


@pytest.fixture()
def conn():
    c = duckdb.connect(":memory:")
    c.execute("INSTALL spatial; LOAD spatial;")
    yield c
    c.close()


class TestZoneU:
    def test_ces_source_categorie_datappro_flag(self, conn):  # cas 1 : zone U nominale
        _create_tables(conn)
        _add_parcelle(conn, "35238000AB0001", "35238")
        _add_plu(conn, "35238", "DU_35238", "U")

        step_gpu(conn, "35")

        row = conn.execute("""
            SELECT source_ces, ces_potentiel, categorie, plu_datappro, zone_non_mutable
            FROM densification_scores WHERE id_parcelle = '35238000AB0001'
        """).fetchone()
        assert row[0] == "plu_gpu"
        assert abs(row[1] - 0.50) < 1e-6, f"CES attendu 0.50, obtenu {row[1]}"
        assert row[2] == "MOYEN"
        assert str(row[3]) == "2022-06-01"
        assert row[4] is False, "zone U ne doit pas lever le flag zone_non_mutable"


class TestPLUi:
    def test_partition_siren_resolue(self, conn):  # cas 2 : PLUi EPCI
        _create_tables(conn)
        _add_parcelle(conn, "35238000AB0002", "35238")
        _add_plu(conn, "35238", "DU_243500139", "AU")

        step_gpu(conn, "35")

        row = conn.execute("""
            SELECT source_ces, ces_potentiel, categorie
            FROM densification_scores WHERE id_parcelle = '35238000AB0002'
        """).fetchone()
        assert row is not None, "PLUi non résolu — partition SIREN non trouvée"
        assert row[0] == "plu_gpu"
        assert abs(row[1] - 0.30) < 1e-6, f"AU doit donner CES 0.30, obtenu {row[1]}"
        assert row[2] == "FORT"


class TestFallbackSansPLU:
    def test_parcelle_reste_inconnu(self, conn):  # cas 3 : commune sans PLU
        _create_tables(conn)
        _add_parcelle(conn, "35238000AB0003", "35238")
        _empty_plu(conn)  # aucun mapping

        step_gpu(conn, "35")

        cat = conn.execute(
            "SELECT categorie FROM densification_scores WHERE id_parcelle = '35238000AB0003'"
        ).fetchone()[0]
        assert cat == "INCONNU", "Sans PLU GPU la parcelle doit rester INCONNU (fallback RNU)"

    def test_commune_no_plu_dans_coverage_issues(self, conn):
        _create_tables(conn)
        _add_parcelle(conn, "35238000AB0004", "35238")
        _empty_plu(conn)

        step_gpu(conn, "35")

        issues = conn.execute(
            "SELECT code_commune, motif FROM plu_coverage_issues"
        ).fetchall()
        assert any(r[0] == "35238" and r[1] == "no_plu_gpu" for r in issues)


class TestPartitionSansZones:
    def test_reste_inconnu_motif_partition_without_zones(self, conn):  # cas 5 (point 4)
        _create_tables(conn)
        _add_parcelle(conn, "35238000AB0005", "35238")
        _empty_plu(conn, map_commune=True)  # mapping ok, zones vides

        step_gpu(conn, "35")

        cat = conn.execute(
            "SELECT categorie FROM densification_scores WHERE id_parcelle = '35238000AB0005'"
        ).fetchone()[0]
        assert cat == "INCONNU", "Partition sans zones : parcelle doit rester INCONNU"
        motifs = [r[0] for r in conn.execute(
            "SELECT motif FROM plu_coverage_issues WHERE code_commune = '35238'"
        ).fetchall()]
        assert "partition_without_zones" in motifs, f"Motif attendu, obtenus: {motifs}"


class TestSousZones:
    @pytest.mark.parametrize("typezone,exp_ces,exp_cat,exp_flag", [
        ("Uh",  0.50, "MOYEN",        False),
        ("AUc", 0.30, "FORT",         False),
        ("Ah",  0.05, "NON_MUTABLE",  True),
        ("Nh",  0.02, "NON_MUTABLE",  True),
    ])
    def test_sous_zone_mappee_sur_parent(self, conn, typezone, exp_ces, exp_cat, exp_flag):  # cas 4
        _create_tables(conn)
        id_p = f"35238000AB{typezone.upper()[:4]:0>4}"
        _add_parcelle(conn, id_p, "35238")
        _add_plu(conn, "35238", "DU_35238", typezone)

        step_gpu(conn, "35")

        row = conn.execute(
            "SELECT ces_potentiel, categorie, zone_non_mutable FROM densification_scores WHERE id_parcelle = ?",
            [id_p],
        ).fetchone()
        assert row is not None, f"Parcelle {id_p} introuvable après step_gpu"
        assert abs(row[0] - exp_ces) < 1e-6, f"{typezone}: CES {row[0]} ≠ {exp_ces}"
        assert row[1] == exp_cat, f"{typezone}: catégorie {row[1]!r} ≠ {exp_cat!r}"
        assert row[2] is exp_flag, f"{typezone}: zone_non_mutable {row[2]} ≠ {exp_flag}"
