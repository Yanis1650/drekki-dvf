"""Step 3: GPU — intégration zones PLU (fichiers locaux).

Corrige les parcelles INCONNU via le PLU en deux étapes :
    1. parcelle.code_commune → plu_commune_partition.partition
    2. partition → plu_zones (ST_Centroid × zone)

Prérequis : import_plu.py doit avoir été exécuté sur cette base.
"""

import logging

import duckdb

from .gpu_diagnostics import _log_diagnostics
from .gpu_matching import _build_matched_parcelles
from .utils import print_distribution, step_banner

logger = logging.getLogger(__name__)


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
