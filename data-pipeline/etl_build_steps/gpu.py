"""Step 3: GPU — intégration zones PLU (fichiers locaux).

Corrige les parcelles INCONNU via le PLU en deux étapes :
    1. parcelle.code_commune → plu_commune_partition.partition
    2. partition → plu_zones (ST_Centroid × zone)

Prérequis : import_plu.py doit avoir été exécuté sur cette base.
"""

import datetime
import logging

import duckdb

from .utils import print_distribution, step_banner

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


def _ensure_columns(conn: duckdb.DuckDBPyConnection) -> None:
    new_cols = (("plu_datappro", "DATE"), ("libelle_zone", "VARCHAR"), ("zone_non_mutable", "BOOLEAN"))
    for col, dtype in new_cols:
        try:
            conn.execute(f"ALTER TABLE densification_scores ADD COLUMN {col} {dtype}")
        except duckdb.CatalogException:
            pass


def _check_plu_tables(conn: duckdb.DuckDBPyConnection) -> bool:
    """Vérifie que les tables PLU prérequises existent.

    Ne vérifie PAS que plu_zones est non-vide : une partition mappée sans zones
    doit passer ici pour être détectée dans _log_diagnostics (motif 'partition_without_zones').
    """
    tables = {r[0] for r in conn.execute("SHOW TABLES").fetchall()}
    missing = {"plu_zones", "plu_commune_partition"} - tables
    if missing:
        print(f"  WARN: tables PLU manquantes {missing} — executer import_plu.py d'abord")
        return False
    return True


def _build_matched_parcelles(conn: duckdb.DuckDBPyConnection, dept: str) -> int:
    """Jointure deux étapes : commune → partition → zone PLU."""
    conn.execute("DROP TABLE IF EXISTS gpu_parcelles")
    conn.execute(f"""
        CREATE TABLE gpu_parcelles AS
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
    """)
    return conn.execute("SELECT COUNT(*) FROM gpu_parcelles").fetchone()[0]


def _update_densification(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("""
        UPDATE densification_scores d SET
            source_ces    = 'plu_gpu',
            ces_potentiel = g.ces_potentiel_plu,
            potentiel_densification = CASE
                WHEN g.ces_actuel IS NOT NULL
                    THEN GREATEST(0.0, g.ces_potentiel_plu - g.ces_actuel)
                ELSE g.ces_potentiel_plu
            END,
            surface_constructible_restante = CASE
                WHEN g.ces_actuel IS NOT NULL
                    THEN GREATEST(0.0, g.ces_potentiel_plu - g.ces_actuel)
                         * d.surface_parcelle_m2
                ELSE g.ces_potentiel_plu * d.surface_parcelle_m2
            END,
            zone_non_mutable = (g.categorie_plu = 'NON_MUTABLE'),
            categorie    = g.categorie_plu,
            libelle_zone = g.libelle_zone,
            plu_datappro = g.datappro
        FROM gpu_parcelles g
        WHERE d.id_parcelle = g.id_parcelle AND d.categorie = 'INCONNU'
    """)


def _log_diagnostics(conn: duckdb.DuckDBPyConnection, dept: str) -> None:
    """Construit plu_coverage_issues et logge tous les problèmes PLU détectés.

    Motifs possibles :
      'no_plu_gpu'            : commune absente de plu_commune_partition
      'partition_without_zones': partition mappée mais aucune zone spatiale trouvée
      'plu_recently_revised'  : PLU approuvé < 180j → re-run ETL recommandé
    """
    cutoff = datetime.date.today() - datetime.timedelta(days=180)
    conn.execute("DROP TABLE IF EXISTS plu_coverage_issues")
    conn.execute(f"""
        CREATE TABLE plu_coverage_issues AS
        SELECT
            d.code_commune,
            COUNT(*) AS parcelles_inconnu,
            CASE WHEN cp.code_commune IS NULL THEN 'no_plu_gpu'
                 ELSE 'partition_without_zones'
            END AS motif
        FROM densification_scores d
        LEFT JOIN plu_commune_partition cp ON d.code_commune = cp.code_commune
        WHERE d.categorie = 'INCONNU' AND d.code_commune LIKE '{dept}%'
        GROUP BY d.code_commune, cp.code_commune
        UNION ALL
        SELECT DISTINCT code_commune, 0, 'plu_recently_revised'
        FROM densification_scores
        WHERE plu_datappro IS NOT NULL AND plu_datappro > DATE '{cutoff}'
          AND code_commune LIKE '{dept}%'
    """)
    issues = conn.execute(
        "SELECT code_commune, parcelles_inconnu, motif FROM plu_coverage_issues ORDER BY motif, parcelles_inconnu DESC"
    ).fetchall()
    for code, n, motif in issues[:20]:
        if motif == 'plu_recently_revised':
            msg = f"commune {code}: PLU recemment revise (datappro <180j) — re-run ETL recommande"
        elif motif == 'partition_without_zones':
            msg = f"commune {code}: partition mappee mais aucune zone PLU trouvee ({n} parcelles INCONNU)"
        else:
            msg = f"commune {code}: aucun PLU GPU, fallback RNU ({n} parcelles)"
        logger.warning(msg)
        print(f"    WARN: {msg}")
    if len(issues) > 20:
        print(f"  ... et {len(issues) - 20} autres entrees (voir plu_coverage_issues)")


def step_gpu(conn: duckdb.DuckDBPyConnection, dept: str) -> None:
    step_banner(3, "GPU - Zones PLU (fichiers locaux via import_plu.py)")
    # Colonnes ajoutées en premier : confidence.py en a besoin même si l'étape GPU est sautée
    _ensure_columns(conn)
    if not _check_plu_tables(conn):
        return
    inconnu = conn.execute(f"""
        SELECT COUNT(*) FROM densification_scores
        WHERE categorie = 'INCONNU' AND code_commune LIKE '{dept}%'
    """).fetchone()[0]
    print(f"  INCONNU avant GPU: {inconnu:,}")
    if inconnu == 0:
        print("  Aucun INCONNU — skip")
        return
    try:
        matched = _build_matched_parcelles(conn, dept)
    except Exception as e:
        if "TopologyException" in str(e) or "InvalidInput" in str(e):
            logger.warning("Géométries invalides dans plu_zones — nettoyage ST_MakeValid puis nouvelle tentative")
            print("  WARN: géométries invalides détectées — correction ST_MakeValid...")
            try:
                conn.execute(
                    "UPDATE plu_zones SET geometry = ST_MakeValid(geometry) "
                    "WHERE NOT ST_IsValid(geometry)"
                )
            except Exception:
                pass
            matched = _build_matched_parcelles(conn, dept)
        else:
            raise
    print(f"  Parcelles matchees PLU: {matched:,} / {inconnu:,}")
    if matched > 0:
        _update_densification(conn)
    conn.execute("DROP TABLE IF EXISTS gpu_parcelles")
    _log_diagnostics(conn, dept)
    print_distribution(conn, "Apres GPU")
