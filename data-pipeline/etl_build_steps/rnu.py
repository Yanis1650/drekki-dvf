"""Step 5: RNU (classification proximite)."""

from .config import DATA_DIR, GRID_SIZE
from .utils import print_distribution, step_banner


def step_rnu(conn, dept, gpkg_path):
    step_banner(5, "RNU (classification proximite)")

    inconnu = conn.execute(
        "SELECT COUNT(*) FROM densification_scores WHERE categorie = 'INCONNU'"
    ).fetchone()[0]
    print(f"  INCONNU restants: {inconnu:,}")

    if inconnu == 0:
        print("  Aucun INCONNU -- skip")
        return

    if gpkg_path is None:
        gpkg_path = DATA_DIR / f"bdtopo_{dept}.gpkg"

    has_bdtopo_table = "bdtopo_bati" in [r[0] for r in conn.execute("SHOW TABLES").fetchall()]

    if not has_bdtopo_table and gpkg_path.exists():
        print("  Chargement batiments BD TOPO pour grille RNU...")
        conn.execute(f"""
            CREATE TEMP TABLE _rnu_bati AS
            SELECT ST_Centroid(geometrie) AS pt
            FROM ST_Read('{gpkg_path.as_posix()}', layer='batiment')
            WHERE geometrie IS NOT NULL
              AND (construction_legere IS NULL OR construction_legere = false)
        """)
    elif has_bdtopo_table:
        conn.execute("""
            CREATE TEMP TABLE _rnu_bati AS
            SELECT ST_Centroid(geometry) AS pt FROM bdtopo_bati
        """)
    else:
        print("  Pas de BD TOPO -- skip RNU")
        return

    bati_count = conn.execute("SELECT COUNT(*) FROM _rnu_bati").fetchone()[0]
    print(f"  Batiments pour grille: {bati_count:,}")

    conn.execute(f"""
        CREATE TEMP TABLE _rnu_grid AS
        SELECT
            FLOOR(ST_X(pt) / {GRID_SIZE})::BIGINT AS gx,
            FLOOR(ST_Y(pt) / {GRID_SIZE})::BIGINT AS gy,
            COUNT(*) AS nb_buildings
        FROM _rnu_bati
        GROUP BY 1, 2
    """)

    conn.execute("""
        CREATE TEMP TABLE _rnu_grid_density AS
        SELECT
            g.gx, g.gy,
            g.nb_buildings + COALESCE(
                (SELECT SUM(g2.nb_buildings) FROM _rnu_grid g2
                 WHERE ABS(g2.gx - g.gx) <= 1 AND ABS(g2.gy - g.gy) <= 1
                   AND NOT (g2.gx = g.gx AND g2.gy = g.gy)),
                0
            ) AS nb_buildings
        FROM _rnu_grid g
    """)

    conn.execute(f"""
        CREATE TEMP TABLE _rnu_classification AS
        WITH parcel_grid AS (
            SELECT d.id_parcelle, d.surface_parcelle_m2,
                   FLOOR(ST_X(ST_Centroid(p.geometry)) / {GRID_SIZE})::BIGINT AS gx,
                   FLOOR(ST_Y(ST_Centroid(p.geometry)) / {GRID_SIZE})::BIGINT AS gy
            FROM densification_scores d
            JOIN parcelles p ON d.id_parcelle = p.id_parcelle
            WHERE d.categorie = 'INCONNU' AND p.geometry IS NOT NULL
        )
        SELECT pg.id_parcelle, pg.surface_parcelle_m2,
            COALESCE(g.nb_buildings, 0) AS nb_nearby,
            CASE
                WHEN COALESCE(g.nb_buildings, 0) >= 10 THEN 'MOYEN'
                WHEN COALESCE(g.nb_buildings, 0) >= 3  THEN 'FAIBLE'
                WHEN COALESCE(g.nb_buildings, 0) >= 1  THEN 'FAIBLE'
                ELSE 'NON_MUTABLE'
            END AS rnu_categorie,
            CASE
                WHEN COALESCE(g.nb_buildings, 0) >= 10 THEN 0.15
                WHEN COALESCE(g.nb_buildings, 0) >= 3  THEN 0.08
                WHEN COALESCE(g.nb_buildings, 0) >= 1  THEN 0.05
                ELSE 0.01
            END AS rnu_potentiel
        FROM parcel_grid pg
        LEFT JOIN _rnu_grid_density g ON pg.gx = g.gx AND pg.gy = g.gy
    """)

    conn.execute("""
        UPDATE densification_scores d SET
            source_ces = 'rnu_proximite',
            potentiel_densification = r.rnu_potentiel,
            surface_constructible_restante = r.rnu_potentiel * r.surface_parcelle_m2,
            categorie = r.rnu_categorie
        FROM _rnu_classification r
        WHERE d.id_parcelle = r.id_parcelle AND d.categorie = 'INCONNU'
    """)

    print_distribution(conn, "Apres RNU")
