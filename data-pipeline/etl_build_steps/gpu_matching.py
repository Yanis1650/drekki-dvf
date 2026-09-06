"""Appariement parcelle -> zone PLU, le coeur SQL de l'etape GPU.

Deux sauts : la commune donne la partition du document d'urbanisme, puis le
centroide de la parcelle est localise dans une zone de cette partition.
"""

import logging

import duckdb

logger = logging.getLogger(__name__)

# Ordre crucial : AU avant A (sinon 'AU' matché par 'A%')
_NORM_SQL = """
    CASE
        WHEN typezone LIKE 'AU%' THEN 'AU'
        WHEN typezone LIKE 'U%'  THEN 'U'
        WHEN typezone LIKE 'A%'  THEN 'A'
        WHEN typezone LIKE 'N%'  THEN 'N'
        ELSE 'autre'
    END
"""


def _build_matched_parcelles(conn: duckdb.DuckDBPyConnection, dept: str) -> int:
    """Jointure deux étapes : commune → partition → zone PLU.

    Traitée partition par partition. En un seul passage, la jointure spatiale
    (800 000 parcelles INCONNU × 22 000 zones, avec un ST_Intersection dans la
    fenêtre de tri) dépasse 25 Gio et DuckDB abandonne. Découper par partition
    borne la mémoire sans changer le résultat : la jointure est de toute façon
    contrainte à `z.partition = wp.partition`, donc aucune paire ne traverse
    deux partitions.
    """
    conn.execute("DROP TABLE IF EXISTS gpu_parcelles")

    partitions = [
        r[0] for r in conn.execute(
            "SELECT DISTINCT partition FROM plu_commune_partition "
            "WHERE partition IS NOT NULL ORDER BY partition"
        ).fetchall()
    ]
    if not partitions:
        conn.execute(_matched_sql(dept, partition=None, create=True))
        return conn.execute("SELECT COUNT(*) FROM gpu_parcelles").fetchone()[0]

    print(f"  Jointure spatiale : {len(partitions)} partitions...")
    for i, part in enumerate(partitions, 1):
        conn.execute(_matched_sql(dept, partition=part, create=(i == 1)))
        if i % 25 == 0 or i == len(partitions):
            done = conn.execute("SELECT COUNT(*) FROM gpu_parcelles").fetchone()[0]
            print(f"    {i}/{len(partitions)} partitions — {done:,} parcelles rattachees")

    # Quelques communes relèvent de deux documents : la parcelle est alors
    # rattachée une fois par partition. Le passage unique dédupliquait via son
    # ROW_NUMBER global ; à découpage égal, on déduplique ici. Sans cela,
    # l'UPDATE en aval retiendrait une ligne arbitraire.
    dupes = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT id_parcelle FROM gpu_parcelles
            GROUP BY id_parcelle HAVING COUNT(*) > 1
        )
    """).fetchone()[0]
    if dupes:
        print(f"  {dupes:,} parcelles couvertes par plusieurs documents — deduplication")
        conn.execute("""
            CREATE OR REPLACE TABLE gpu_parcelles AS
            SELECT * EXCLUDE (rn) FROM (
                SELECT *, ROW_NUMBER() OVER (
                    PARTITION BY id_parcelle
                    -- Le document le plus récent fait foi.
                    ORDER BY datappro DESC NULLS LAST
                ) AS rn
                FROM gpu_parcelles
            ) WHERE rn = 1
        """)

    return conn.execute("SELECT COUNT(*) FROM gpu_parcelles").fetchone()[0]


def _matched_sql(dept: str, partition: str | None, create: bool) -> str:
    """Construit la requête de rattachement, pour une partition ou toutes."""
    head = "CREATE TABLE gpu_parcelles AS" if create else "INSERT INTO gpu_parcelles"
    part_filter = f"AND cp.partition = '{partition}'" if partition else ""
    return f"""
        {head}
        WITH inconnu AS (
            SELECT d.id_parcelle, d.surface_parcelle_m2, d.ces_actuel,
                   p.geometry, p.code_commune
            FROM densification_scores d
            JOIN parcelles p ON d.id_parcelle = p.id_parcelle
            WHERE d.categorie = 'INCONNU' AND p.geometry IS NOT NULL
              AND d.code_commune LIKE '{dept}%'
        ),
        with_partition AS (
            -- Résout PLU communaux (DU_INSEE) ET PLUi EPCI (DU_SIREN)
            SELECT i.*, cp.partition
            FROM inconnu i
            JOIN plu_commune_partition cp ON i.code_commune = cp.code_commune
            {part_filter}
        ),
        matched AS (
            SELECT
                wp.id_parcelle, wp.code_commune,
                wp.surface_parcelle_m2, wp.ces_actuel,
                z.typezone, z.libelle AS libelle_zone, z.datappro,
                ({_NORM_SQL}) AS parent_zone,
                ROW_NUMBER() OVER (
                    PARTITION BY wp.id_parcelle
                    ORDER BY ST_Area(ST_Intersection(wp.geometry, z.geometry)) DESC
                ) AS rn
            FROM with_partition wp
            JOIN plu_zones z
              ON  z.partition = wp.partition
              AND ST_Intersects(ST_Centroid(wp.geometry), z.geometry)
        )
        SELECT
            id_parcelle, code_commune, surface_parcelle_m2, ces_actuel,
            typezone, libelle_zone, datappro, parent_zone,
            CASE parent_zone
                WHEN 'U' THEN 0.50 WHEN 'AU' THEN 0.30
                WHEN 'A' THEN 0.05 WHEN 'N'  THEN 0.02 ELSE 0.40
            END AS ces_potentiel_plu,
            CASE parent_zone
                WHEN 'A' THEN 'NON_MUTABLE' WHEN 'N' THEN 'NON_MUTABLE'
                WHEN 'AU' THEN 'FORT'        WHEN 'U' THEN 'MOYEN'
                ELSE 'FAIBLE'
            END AS categorie_plu
        FROM matched WHERE rn = 1
    """
