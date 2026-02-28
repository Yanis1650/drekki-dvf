"""Step 4: BD TOPO (emprise batie)."""

from .config import DATA_DIR
from .utils import print_distribution, step_banner


def step_bdtopo(conn, dept, gpkg_path):
    step_banner(4, "BD TOPO (emprise batie)")

    if gpkg_path is None:
        gpkg_path = DATA_DIR / f"bdtopo_{dept}.gpkg"

    if not gpkg_path.exists():
        print(f"  BD TOPO non trouvee: {gpkg_path}")
        print(f"  -> Telecharger depuis https://geoservices.ign.fr/bdtopo")
        print(f"  -> Theme BATI, Dept {dept}, format GeoPackage")
        return

    print(f"  BD TOPO: {gpkg_path.name} ({gpkg_path.stat().st_size / 1e9:.1f} GB)")

    inconnu_before = conn.execute(
        "SELECT COUNT(*) FROM densification_scores WHERE categorie = 'INCONNU'"
    ).fetchone()[0]
    print(f"  INCONNU avant: {inconnu_before:,}")

    if inconnu_before == 0:
        print("  Aucun INCONNU restant -- skip")
        return

    conn.execute("DROP TABLE IF EXISTS bdtopo_bati")
    conn.execute(f"""
        CREATE TABLE bdtopo_bati AS
        SELECT
            cleabs AS id_bdtopo, nature, usage_1,
            CAST(hauteur AS DOUBLE) AS hauteur_m,
            CAST(nombre_d_etages AS INTEGER) AS nb_etages,
            ST_Area(geometrie) AS emprise_m2,
            geometrie AS geometry
        FROM ST_Read('{gpkg_path.as_posix()}', layer='batiment')
        WHERE (construction_legere IS NULL OR construction_legere = false)
          AND (etat_de_l_objet IS NULL OR etat_de_l_objet != 'Detruit')
          AND geometrie IS NOT NULL
    """)

    bati_count = conn.execute("SELECT COUNT(*) FROM bdtopo_bati").fetchone()[0]
    print(f"  Batiments charges: {bati_count:,}")

    conn.execute("DROP TABLE IF EXISTS _bdtopo_parcelle")
    conn.execute("""
        CREATE TEMP TABLE _bdtopo_parcelle AS
        SELECT
            p.id_parcelle,
            SUM(b.emprise_m2) AS emprise_bdtopo_m2,
            MAX(b.hauteur_m) AS hauteur_max_m,
            MAX(b.nb_etages) AS nb_etages_max,
            COUNT(*) AS nb_batiments,
            MAX(b.usage_1) AS usage_dominant
        FROM parcelles p
        JOIN bdtopo_bati b ON ST_Intersects(p.geometry, b.geometry)
        WHERE p.id_parcelle IN (
            SELECT id_parcelle FROM densification_scores WHERE categorie = 'INCONNU'
        )
        GROUP BY p.id_parcelle
    """)

    matched = conn.execute("SELECT COUNT(*) FROM _bdtopo_parcelle").fetchone()[0]
    print(f"  Parcelles INCONNU avec bati BD TOPO: {matched:,}")

    conn.execute("""
        CREATE TEMP TABLE _bdtopo_update AS
        SELECT
            bp.id_parcelle,
            bp.emprise_bdtopo_m2,
            CASE
                WHEN bp.nb_etages_max IS NOT NULL
                    THEN bp.emprise_bdtopo_m2 * bp.nb_etages_max
                WHEN bp.hauteur_max_m IS NOT NULL
                    THEN bp.emprise_bdtopo_m2 * GREATEST(1, ROUND(bp.hauteur_max_m / 3.0))
                ELSE bp.emprise_bdtopo_m2
            END AS surface_plancher_est,
            LEAST(bp.emprise_bdtopo_m2 / NULLIF(d.surface_parcelle_m2, 0), 1.0) AS ces_actuel,
            0.40 AS ces_potentiel,
            GREATEST(0.0, 0.40 - LEAST(bp.emprise_bdtopo_m2 / NULLIF(d.surface_parcelle_m2, 0), 1.0)) AS potentiel,
            GREATEST(0.0, 0.40 - LEAST(bp.emprise_bdtopo_m2 / NULLIF(d.surface_parcelle_m2, 0), 1.0))
                * d.surface_parcelle_m2 AS surface_constr,
            CASE
                WHEN GREATEST(0.0, 0.40 - LEAST(bp.emprise_bdtopo_m2 / NULLIF(d.surface_parcelle_m2, 0), 1.0)) >= 0.25 THEN 'FORT'
                WHEN GREATEST(0.0, 0.40 - LEAST(bp.emprise_bdtopo_m2 / NULLIF(d.surface_parcelle_m2, 0), 1.0)) >= 0.10 THEN 'MOYEN'
                WHEN GREATEST(0.0, 0.40 - LEAST(bp.emprise_bdtopo_m2 / NULLIF(d.surface_parcelle_m2, 0), 1.0)) > 0.02  THEN 'FAIBLE'
                ELSE 'SATURE'
            END AS new_categorie
        FROM _bdtopo_parcelle bp
        JOIN densification_scores d ON bp.id_parcelle = d.id_parcelle
    """)

    conn.execute("""
        UPDATE densification_scores d SET
            source_ces = 'bdtopo',
            emprise_sol_m2 = u.emprise_bdtopo_m2,
            surface_plancher_m2 = u.surface_plancher_est,
            ces_actuel = u.ces_actuel,
            ces_potentiel = u.ces_potentiel,
            potentiel_densification = u.potentiel,
            surface_constructible_restante = u.surface_constr,
            categorie = u.new_categorie
        FROM _bdtopo_update u
        WHERE d.id_parcelle = u.id_parcelle AND d.categorie = 'INCONNU'
    """)

    conn.execute("DROP TABLE IF EXISTS bdtopo_bati")
    print_distribution(conn, "Apres BD TOPO")
