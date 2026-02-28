"""Step 1: Golden Join (mutations x parcelles x BDNB)."""
import duckdb

from .config import BDNB_PARQUET, MAIN_DB
from .utils import step_banner


def step_golden_join(conn, dept):
    step_banner(1, "Golden Join (mutations x parcelles x BDNB)")

    main_conn = duckdb.connect(str(MAIN_DB), read_only=True)
    main_conn.execute("LOAD spatial;")

    mut_count = main_conn.execute(
        f"SELECT COUNT(*) FROM mutations_aggregated WHERE code_commune LIKE '{dept}%'"
    ).fetchone()[0]
    print(f"  Mutations dept {dept}: {mut_count:,}")

    if mut_count == 0:
        print(f"  ERREUR: Aucune mutation pour le dept {dept}")
        main_conn.close()
        return False

    parc_count = main_conn.execute(f"""
        SELECT COUNT(*) FROM parcelles
        WHERE code_commune LIKE '{dept}%' AND section IS NOT NULL AND numero IS NOT NULL
    """).fetchone()[0]
    print(f"  Parcelles leaf dept {dept}: {parc_count:,}")

    print("  Export mutations...")
    conn.execute(f"""
        CREATE TABLE mutations_aggregated AS
        SELECT * FROM main_db.mutations_aggregated
        WHERE code_commune LIKE '{dept}%'
    """)

    print("  Export parcelles...")
    conn.execute(f"""
        CREATE TABLE parcelles AS
        SELECT * FROM main_db.parcelles
        WHERE code_commune LIKE '{dept}%'
    """)

    has_bdnb = BDNB_PARQUET.exists()
    if has_bdnb:
        print("  Export BDNB...")
        conn.execute(f"""
            CREATE TABLE bdnb_stats AS
            SELECT * FROM read_parquet('{BDNB_PARQUET.as_posix()}')
            WHERE parcelle_id LIKE '{dept}%'
        """)
        bdnb_count = conn.execute("SELECT COUNT(*) FROM bdnb_stats").fetchone()[0]
        print(f"  BDNB: {bdnb_count:,}")

    main_conn.close()

    print("  Spatial join...")
    bdnb_cols = (
        "b.dpe_energie, b.annee_construction, b.hauteur_moyenne, "
        "b.nb_niveau, b.type_usage, b.nb_log"
    ) if has_bdnb else (
        "NULL AS dpe_energie, NULL AS annee_construction, "
        "NULL AS hauteur_moyenne, NULL AS nb_niveau, "
        "NULL AS type_usage, NULL AS nb_log"
    )
    bdnb_join = "LEFT JOIN bdnb_stats b ON mp.id_parcelle = b.parcelle_id" if has_bdnb else ""

    conn.execute(f"""
        CREATE TABLE france_foncier_test AS
        WITH mutations_dept AS (
            SELECT m.*,
                   ST_Transform(ST_Point(m.latitude, m.longitude),
                                'EPSG:4326', 'EPSG:2154') AS point_geom
            FROM mutations_aggregated m
            WHERE m.longitude IS NOT NULL AND m.latitude IS NOT NULL
        ),
        parcelles_dept AS (
            SELECT * FROM parcelles
            WHERE section IS NOT NULL AND numero IS NOT NULL
        ),
        mutation_parcelle_ranked AS (
            SELECT md.*, pd.id_parcelle, pd.geometry AS parcelle_geometry,
                   ROW_NUMBER() OVER (PARTITION BY md.id_mutation
                                      ORDER BY ST_Area(pd.geometry) ASC) AS rn
            FROM mutations_dept md
            LEFT JOIN parcelles_dept pd
                ON md.code_commune = pd.code_commune
                AND ST_Contains(pd.geometry, md.point_geom)
        ),
        mutation_parcelle AS (
            SELECT * FROM mutation_parcelle_ranked WHERE rn = 1
        )
        SELECT
            mp.id_mutation, mp.date_mutation, mp.nature_mutation,
            mp.valeur_fonciere, mp.code_commune,
            mp.parcelles AS dvf_parcelles,
            mp.surface_habitable_totale, mp.nombre_locaux, mp.prix_m2,
            mp.longitude, mp.latitude,
            mp.id_parcelle AS cadastre_parcelle_id,
            mp.parcelle_geometry AS geometry,
            {bdnb_cols}
        FROM mutation_parcelle mp
        {bdnb_join}
    """)

    count = conn.execute("SELECT COUNT(*) FROM france_foncier_test").fetchone()[0]
    print(f"  france_foncier_test: {count:,} rows")

    conn.execute("CREATE INDEX idx_fft_date ON france_foncier_test(date_mutation)")
    conn.execute("CREATE INDEX idx_fft_commune ON france_foncier_test(code_commune)")
    conn.execute("CREATE INDEX idx_fft_parcelle ON france_foncier_test(cadastre_parcelle_id)")

    return True
