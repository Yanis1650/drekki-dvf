"""Step 4: BD TOPO (emprise batie)."""

import tempfile
from pathlib import Path

import geopandas as gpd
from shapely.geometry import shape
from shapely.validation import make_valid

from .config import DATA_DIR
from .utils import print_distribution, step_banner


def _load_bdtopo_filtered(gpkg_path: Path) -> Path:
    """Charge BD TOPO avec GeoPandas, filtre geometries corrompues, ecrit un gpkg propre."""
    print("  Chargement BD TOPO (filtrage geometries corrompues)...")
    import fiona

    rows = []
    skipped = 0
    crs_wkt = None
    with fiona.open(gpkg_path, layer="batiment") as src:
        crs_wkt = src.crs_wkt
        it = iter(src)
        while True:
            try:
                feat = next(it)
            except StopIteration:
                break
            except (ValueError, TypeError, KeyError):
                skipped += 1
                continue
            if feat.get("properties", {}).get("construction_legere"):
                continue
            if feat.get("properties", {}).get("etat_de_l_objet") == "Detruit":
                continue
            try:
                geom = shape(feat["geometry"])
                if geom is None or geom.is_empty:
                    skipped += 1
                    continue
                if not geom.is_valid:
                    geom = make_valid(geom)
                if geom is None or geom.is_empty:
                    skipped += 1
                    continue
                props = feat.get("properties", {})
                rows.append(
                    {
                        "cleabs": props.get("cleabs"),
                        "nature": props.get("nature"),
                        "usage_1": props.get("usage_1"),
                        "hauteur": props.get("hauteur"),
                        "nombre_d_etages": props.get("nombre_d_etages"),
                        "geometry": geom,
                    }
                )
            except Exception:
                skipped += 1

    if not rows:
        raise ValueError("Aucun batiment valide dans le fichier BD TOPO")
    if skipped:
        print(f"  Geometries ignorees (corrompues/invalides): {skipped:,}")

    gdf = gpd.GeoDataFrame(rows, crs=crs_wkt or "EPSG:2154")
    tmp = Path(tempfile.gettempdir()) / f"bdtopo_bati_clean_{gpkg_path.stem}.gpkg"
    gdf.to_file(tmp, driver="GPKG", layer="batiment")
    return tmp


def step_bdtopo(conn, dept, gpkg_path):
    step_banner(4, "BD TOPO (emprise batie)")

    if gpkg_path is None:
        gpkg_path = DATA_DIR / f"bdtopo_{dept}.gpkg"

    if not gpkg_path.exists():
        print(f"  BD TOPO non trouvee: {gpkg_path}")
        print("  -> Telecharger depuis https://geoservices.ign.fr/bdtopo")
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

    clean_path = _load_bdtopo_filtered(gpkg_path)

    conn.execute("DROP TABLE IF EXISTS bdtopo_bati")
    conn.execute(f"""
        CREATE TABLE bdtopo_bati AS
        SELECT
            cleabs AS id_bdtopo, nature, usage_1,
            CAST(hauteur AS DOUBLE) AS hauteur_m,
            CAST(nombre_d_etages AS INTEGER) AS nb_etages,
            ST_Area(geom) AS emprise_m2,
            geom AS geometry
        FROM ST_Read('{clean_path.as_posix()}', layer='batiment')
    """)
    try:
        clean_path.unlink(missing_ok=True)
    except OSError:
        pass

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
            -- Potentiel restant = CES cible (0.40) moins le CES deja bati,
            -- borne a [0, 0.40]. Facteur commun aux trois seuils ci-dessous.
            CASE
                WHEN GREATEST(0.0, 0.40 - LEAST(
                        bp.emprise_bdtopo_m2 / NULLIF(d.surface_parcelle_m2, 0), 1.0
                     )) >= 0.25 THEN 'FORT'
                WHEN GREATEST(0.0, 0.40 - LEAST(
                        bp.emprise_bdtopo_m2 / NULLIF(d.surface_parcelle_m2, 0), 1.0
                     )) >= 0.10 THEN 'MOYEN'
                WHEN GREATEST(0.0, 0.40 - LEAST(
                        bp.emprise_bdtopo_m2 / NULLIF(d.surface_parcelle_m2, 0), 1.0
                     )) > 0.02 THEN 'FAIBLE'
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
