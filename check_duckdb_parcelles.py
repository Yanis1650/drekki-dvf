"""Check DuckDB parcelles table directly"""
import duckdb

conn = duckdb.connect('data/foncier.duckdb', read_only=True)
conn.execute('INSTALL spatial; LOAD spatial;')

# Get all tables
tables = [t[0] for t in conn.execute('SHOW TABLES').fetchall()]
print(f"Tables in database: {tables}")

# Check if parcelles exists
if 'parcelles' in tables:
    print("\n✅ Table 'parcelles' EXISTS")

    # Get total count
    total = conn.execute('SELECT COUNT(*) FROM parcelles').fetchone()[0]
    print(f"   Total parcelles: {total:,}")

    # Get dept 35 count
    count_35 = conn.execute("SELECT COUNT(*) FROM parcelles WHERE code_commune LIKE '35%'").fetchone()[0]
    print(f"   Dept 35 parcelles: {count_35:,}")

    if count_35 == 0:
        print("\n⚠️  No parcelles for dept 35!")
        print("   Need to load cadastral data for Ille-et-Vilaine")

        # Check what departments we have
        print("\n   Checking available departments...")
        sample_depts = conn.execute("""
            SELECT DISTINCT SUBSTRING(code_commune, 1, 2) as dept, COUNT(*) as count
            FROM parcelles 
            GROUP BY dept 
            ORDER BY count DESC 
            LIMIT 10
        """).fetchall()
        print("   Top 10 departments:")
        for dept, count in sample_depts:
            print(f"      Dept {dept}: {count:,} parcelles")
else:
    print("\n❌ Table 'parcelles' DOES NOT EXIST")
    print("   Need to run: python data-pipeline/etl_france_cadastre.py")

conn.close()
