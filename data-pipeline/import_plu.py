"""Import PLU/PLUi GeoPackage GPU vers DuckDB.

Construit deux tables :
  - plu_commune_partition : code_commune (INSEE) → partition GPU
  - plu_zones             : partition, typezone, libelle, datappro, geometry

Ces tables sont prérequises pour l'étape 3 du pipeline ETL (gpu.py).
Elles résolvent le problème PLUi : les communes membres d'un EPCI ont une
partition de type DU_<SIREN_EPCI> et non DU_<INSEE>, ce qui rendait la
jointure directe impossible.

Usage:
    python import_plu.py 35 --db data/dept35.duckdb --gpkg data/plu_35.gpkg
    python import_plu.py 35 --db data/dept35.duckdb --download
"""

import argparse
import logging
import sys
import urllib.request
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)

GPU_PACK_URL = "https://data.geopf.fr/telechargement/resource/pack_plu"
_APPROVED_STATES = ("Approuvé", "Opposable", "Applicable", "En vigueur")


def download_gpkg(url: str, dest: Path, label: str) -> bool:
    """Télécharge un GeoPackage GPU depuis la Géoplateforme IGN."""
    print(f"  Telechargement {label} -> {dest.name}")
    try:
        urllib.request.urlretrieve(url, dest)
        print(f"  OK: {dest.stat().st_size / 1e6:.0f} MB")
        return True
    except Exception as e:
        print(f"  ERREUR telechargement {label}: {e}")
        return False


def _detect_insee_field(conn: duckdb.DuckDBPyConnection, gpkg_str: str) -> str:
    """Détecte le nom du champ commune dans doc_urba (CNIG 2014: 'insee', récent: 'code_commune')."""
    for field in ("insee", "code_commune", "code_insee"):
        try:
            conn.execute(f"SELECT {field} FROM ST_Read('{gpkg_str}', layer='doc_urba') LIMIT 1")
            return field
        except Exception:
            continue
    logger.warning("Champ commune introuvable dans doc_urba — fallback 'insee'")
    return "insee"


def _import_commune_partition(conn: duckdb.DuckDBPyConnection, gpkg_str: str, dept: str) -> int:
    """Construit plu_commune_partition depuis doc_urba (couvre PLU communaux et PLUi EPCI)."""
    conn.execute("DROP TABLE IF EXISTS plu_commune_partition")
    field = _detect_insee_field(conn, gpkg_str)

    # Validation de contenu : détecter les codes INSEE NULL ou de longueur anormale.
    # Ces lignes sont exclues du mapping mais n'interrompent pas l'import.
    try:
        nulls, bad_len, total_raw = conn.execute(f"""
            SELECT
                COUNT(*) FILTER (WHERE {field} IS NULL),
                COUNT(*) FILTER (WHERE {field} IS NOT NULL
                    AND LEN(CAST({field} AS VARCHAR)) NOT IN (4, 5)),
                COUNT(*)
            FROM ST_Read('{gpkg_str}', layer='doc_urba')
        """).fetchone()
        if nulls:
            logger.warning("doc_urba: %d/%d lignes avec %s NULL — ignorees", nulls, total_raw, field)
            print(f"  WARN: {nulls}/{total_raw} lignes avec {field} NULL ignorees")
        if bad_len:
            logger.warning("doc_urba: %d lignes longueur INSEE invalide — ignorees", bad_len)
            print(f"  WARN: {bad_len} lignes avec LEN({field}) hors (4,5) ignorees")
    except Exception as e:
        logger.warning("Validation contenu doc_urba impossible: %s", e)

    try:
        conn.execute(f"""
            CREATE TABLE plu_commune_partition AS
            SELECT DISTINCT
                CAST({field} AS VARCHAR) AS code_commune,
                CAST(partition AS VARCHAR) AS partition
            FROM ST_Read('{gpkg_str}', layer='doc_urba')
            WHERE CAST({field} AS VARCHAR) LIKE '{dept}%'
              AND {field} IS NOT NULL
              AND LEN(CAST({field} AS VARCHAR)) IN (4, 5)
              AND partition IS NOT NULL
              AND (etat IS NULL OR etat IN {tuple(_APPROVED_STATES)})
        """)
    except Exception as e:
        logger.error("Echec lecture doc_urba: %s", e)
        conn.execute("CREATE TABLE plu_commune_partition (code_commune VARCHAR, partition VARCHAR)")
        print(f"  WARN: doc_urba non lisible ({e}) — table vide creee")
        return 0

    conn.execute("CREATE INDEX idx_pcp_commune ON plu_commune_partition(code_commune)")
    count = conn.execute("SELECT COUNT(*) FROM plu_commune_partition").fetchone()[0]
    parts = conn.execute("SELECT COUNT(DISTINCT partition) FROM plu_commune_partition").fetchone()[0]
    print(f"  plu_commune_partition: {count} communes, {parts} partitions (dont PLUi) — champ '{field}'")
    return count


def _import_plu_zones(conn: duckdb.DuckDBPyConnection, gpkg_str: str) -> int:
    """Construit plu_zones depuis zone_urba, filtré sur les partitions connues."""
    partitions = conn.execute("SELECT DISTINCT partition FROM plu_commune_partition").fetchall()
    if not partitions:
        conn.execute("CREATE TABLE plu_zones "
                     "(partition VARCHAR, typezone VARCHAR, libelle VARCHAR, datappro DATE, geometry GEOMETRY)")
        return 0
    part_list = ", ".join(f"'{r[0]}'" for r in partitions)
    conn.execute("DROP TABLE IF EXISTS plu_zones")
    try:
        conn.execute(f"""
            CREATE TABLE plu_zones AS
            SELECT
                CAST(partition AS VARCHAR) AS partition,
                CAST(typezone  AS VARCHAR) AS typezone,
                CAST(libelle   AS VARCHAR) AS libelle,
                TRY_CAST(datappro AS DATE) AS datappro,
                geom AS geometry
            FROM ST_Read('{gpkg_str}', layer='zone_urba')
            WHERE partition IN ({part_list}) AND typezone IS NOT NULL AND geom IS NOT NULL
        """)
    except Exception as e:
        logger.error("Echec lecture zone_urba: %s", e)
        conn.execute("CREATE TABLE plu_zones "
                     "(partition VARCHAR, typezone VARCHAR, libelle VARCHAR, datappro DATE, geometry GEOMETRY)")
        print(f"  WARN: zone_urba non lisible ({e}) — table vide creee")
        return 0
    conn.execute("CREATE INDEX idx_pz_partition ON plu_zones(partition)")

    # Nettoyer les géométries invalides (fréquent dans les PLUi CNIG)
    try:
        invalid = conn.execute(
            "SELECT COUNT(*) FROM plu_zones WHERE NOT ST_IsValid(geometry)"
        ).fetchone()[0]
        if invalid:
            conn.execute(
                "UPDATE plu_zones SET geometry = ST_MakeValid(geometry) "
                "WHERE NOT ST_IsValid(geometry)"
            )
            logger.info("ST_MakeValid appliqué sur %d géométries invalides", invalid)
            print(f"  Geometries invalides corrigees: {invalid}")
    except Exception as e:
        logger.warning("Verification ST_IsValid impossible: %s", e)

    count = conn.execute("SELECT COUNT(*) FROM plu_zones").fetchone()[0]
    print(f"  plu_zones: {count:,} zones importees")
    return count


def import_plu_into_duckdb(conn: duckdb.DuckDBPyConnection, gpkg_path: Path, dept: str) -> dict[str, int]:
    """Orchestre l'import des deux tables PLU dans une base DuckDB existante."""
    gpkg_str = gpkg_path.as_posix()
    communes = _import_commune_partition(conn, gpkg_str, dept)
    zones = _import_plu_zones(conn, gpkg_str)
    return {"communes": communes, "zones": zones}


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Import PLU GPU -> DuckDB")
    parser.add_argument("dept", help="Code departement (ex: 35, 29, 2A)")
    parser.add_argument("--db", type=Path, required=True, help="Chemin DuckDB cible")
    parser.add_argument("--gpkg", type=Path, default=None, help="GeoPackage GPU local")
    parser.add_argument("--download", action="store_true", help="Telecharger depuis Geoplateforme")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"ERREUR: base DuckDB non trouvee: {args.db}", file=sys.stderr)
        sys.exit(1)

    gpkg_path = args.gpkg or (args.db.parent / f"plu_{args.dept}.gpkg")
    if not gpkg_path.exists():
        if not args.download:
            print(f"ERREUR: {gpkg_path} introuvable — utilisez --download ou --gpkg.", file=sys.stderr)
            sys.exit(1)
        if not download_gpkg(GPU_PACK_URL, gpkg_path, f"PLU dept {args.dept}"):
            sys.exit(1)

    print(f"Import PLU dept {args.dept} | {gpkg_path.name} ({gpkg_path.stat().st_size/1e6:.0f} MB) -> {args.db.name}")
    conn = duckdb.connect(str(args.db))
    conn.execute("INSTALL spatial; LOAD spatial;")
    result = import_plu_into_duckdb(conn, gpkg_path, args.dept)
    conn.close()
    print(f"Termine: {result['communes']} communes, {result['zones']} zones")


if __name__ == "__main__":
    main()
