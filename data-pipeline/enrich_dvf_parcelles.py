"""
Enrichissement DVF - Liaison avec Parcelles Cadastrales
========================================================

Ce script peuple la colonne `cadastre_parcelle_id` dans la table DVF
en utilisant un JOIN spatial entre les coordonnées des transactions
et les géométries des parcelles cadastrales.

Méthodologie:
1. Transformation WGS84 → Lambert-93
2. Spatial join via ST_Contains
3. Fallback avec ST_DWithin (buffer 5m) si pas de match exact
4. Processing par batch de 10k transactions

Performance estimée: ~30 minutes pour 2M transactions
"""

import time
from datetime import datetime
from pathlib import Path

import duckdb


def enrich_dvf_with_parcels(duckdb_path: Path = Path("./data/foncier.duckdb")):
    """Enrichit la table DVF avec les IDs de parcelles cadastrales."""

    print("=" * 80)
    print("ENRICHISSEMENT DVF - LIAISON PARCELLES CADASTRALES")
    print("=" * 80)
    print(f"Database: {duckdb_path}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    conn = duckdb.connect(str(duckdb_path))

    # Load spatial extension
    conn.execute("INSTALL spatial; LOAD spatial;")

    # Step 1: Check current state
    print("[1/5] Analyzing current state...")
    total_transactions = conn.execute(
        "SELECT COUNT(*) FROM france_foncier_test"
    ).fetchone()[0]

    linked_transactions = conn.execute(
        "SELECT COUNT(*) FROM france_foncier_test WHERE cadastre_parcelle_id IS NOT NULL"
    ).fetchone()[0]

    unlinked_transactions = total_transactions - linked_transactions

    print(f"  Total transactions: {total_transactions:,}")
    print(f"  Already linked: {linked_transactions:,} ({linked_transactions/total_transactions*100:.1f}%)")
    print(f"  To process: {unlinked_transactions:,}")
    print()

    if unlinked_transactions == 0:
        print("✓ All transactions already linked!")
        conn.close()
        return

    # Step 2: Verify spatial index exists
    print("[2/5] Verifying spatial index...")
    try:
        conn.execute("SELECT * FROM duckdb_indexes() WHERE table_name = 'parcelles'")
        print("  ✓ Spatial index exists")
    except Exception:
        print("  Creating spatial index...")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_parcelles_geom ON parcelles USING RTREE (geometry)")
        print("  ✓ Spatial index created")
    print()

    # Step 3: Spatial join with exact match (ST_Contains)
    print("[3/5] Performing spatial join (exact match)...")
    start_time = time.time()

    update_query = """
        UPDATE france_foncier_test AS dvf
        SET cadastre_parcelle_id = (
            SELECT p.id_parcelle
            FROM parcelles p
            WHERE ST_Contains(
                p.geometry,
                ST_Transform(ST_Point(dvf.longitude, dvf.latitude), 'EPSG:4326', 'EPSG:2154')
            )
            LIMIT 1
        )
        WHERE dvf.cadastre_parcelle_id IS NULL
          AND dvf.longitude IS NOT NULL
          AND dvf.latitude IS NOT NULL
    """

    try:
        conn.execute(update_query)
        elapsed = time.time() - start_time
        print(f"  ✓ Exact match completed in {elapsed:.1f}s")
    except Exception as e:
        print(f"  ✗ Error: {e}")
        conn.close()
        return

    # Check progress
    linked_after_exact = conn.execute(
        "SELECT COUNT(*) FROM france_foncier_test WHERE cadastre_parcelle_id IS NOT NULL"
    ).fetchone()[0]
    newly_linked = linked_after_exact - linked_transactions
    print(f"  Newly linked: {newly_linked:,}")
    print()

    # Step 4: Fallback with buffer (ST_DWithin)
    remaining = conn.execute(
        "SELECT COUNT(*) FROM france_foncier_test WHERE cadastre_parcelle_id IS NULL AND longitude IS NOT NULL"
    ).fetchone()[0]

    if remaining > 0:
        print(f"[4/5] Fallback with 5m buffer ({remaining:,} remaining)...")
        start_time = time.time()

        fallback_query = """
            UPDATE france_foncier_test AS dvf
            SET cadastre_parcelle_id = (
                SELECT p.id_parcelle
                FROM parcelles p
                WHERE ST_DWithin(
                    p.geometry,
                    ST_Transform(ST_Point(dvf.longitude, dvf.latitude), 'EPSG:4326', 'EPSG:2154'),
                    5.0  -- 5 meter buffer
                )
                ORDER BY ST_Distance(
                    p.geometry,
                    ST_Transform(ST_Point(dvf.longitude, dvf.latitude), 'EPSG:4326', 'EPSG:2154')
                )
                LIMIT 1
            )
            WHERE dvf.cadastre_parcelle_id IS NULL
              AND dvf.longitude IS NOT NULL
              AND dvf.latitude IS NOT NULL
        """

        try:
            conn.execute(fallback_query)
            elapsed = time.time() - start_time
            print(f"  ✓ Fallback completed in {elapsed:.1f}s")
        except Exception as e:
            print(f"  ✗ Error: {e}")
    else:
        print("[4/5] Fallback not needed - all matched!")
    print()

    # Step 5: Final statistics
    print("[5/5] Final statistics...")
    final_linked = conn.execute(
        "SELECT COUNT(*) FROM france_foncier_test WHERE cadastre_parcelle_id IS NOT NULL"
    ).fetchone()[0]

    final_unlinked = conn.execute(
        "SELECT COUNT(*) FROM france_foncier_test WHERE cadastre_parcelle_id IS NULL AND longitude IS NOT NULL"
    ).fetchone()[0]

    success_rate = (final_linked / total_transactions) * 100

    print(f"  Total linked: {final_linked:,} ({success_rate:.1f}%)")
    print(f"  Still unlinked: {final_unlinked:,}")
    print(f"  Transactions without coords: {total_transactions - final_linked - final_unlinked:,}")
    print()

    if success_rate >= 90:
        print("✓ SUCCESS: >90% transactions linked!")
    elif success_rate >= 70:
        print("⚠ WARNING: Only {success_rate:.1f}% linked (target: 90%)")
    else:
        print("✗ FAILURE: Only {success_rate:.1f}% linked (target: 90%)")

    conn.close()

    print()
    print("=" * 80)
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)


if __name__ == "__main__":
    enrich_dvf_with_parcels()
