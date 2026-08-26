"""Add index on date_mutation for analytics performance.

Run this script to optimize market trends queries.
"""

from pathlib import Path

import duckdb

DUCKDB_PATH = Path("data/foncier.duckdb")


def main():
    print("=" * 60)
    print("Adding Index on date_mutation for Analytics")
    print("=" * 60)

    conn = duckdb.connect(str(DUCKDB_PATH))

    # Check if table exists
    tables = conn.execute("SHOW TABLES").fetchall()
    table_names = [t[0] for t in tables]

    if 'france_foncier_test' not in table_names:
        print("ERROR: france_foncier_test table not found")
        print(f"Available tables: {table_names}")
        conn.close()
        return

    print("\nCreating index on date_mutation column...")

    try:
        # Create index
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_date_mutation
            ON france_foncier_test(date_mutation)
        """)
        print("✅ Index created successfully")

        # Verify
        count = conn.execute("""
            SELECT COUNT(*) FROM france_foncier_test
        """).fetchone()[0]
        print(f"   Table has {count:,} rows")

        # Test query performance
        print("\nTesting query performance...")
        import time
        start = time.time()

        result = conn.execute("""
            SELECT
                YEAR(date_mutation) as year,
                AVG(prix_m2) as avg_price,
                COUNT(*) as volume
            FROM france_foncier_test
            WHERE date_mutation >= '2020-01-01'
              AND prix_m2 IS NOT NULL
            GROUP BY year
            ORDER BY year
        """).fetchall()

        elapsed = time.time() - start
        print(f"   Query completed in {elapsed:.3f}s")
        print(f"   Found {len(result)} years of data")

    except Exception as e:
        print(f"ERROR: {e}")

    conn.close()
    print("\n✅ Optimization complete")


if __name__ == "__main__":
    main()
