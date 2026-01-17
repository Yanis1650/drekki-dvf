"""Quick schema inspection for cadastre.parquet"""
import duckdb

conn = duckdb.connect()
conn.execute("INSTALL spatial; LOAD spatial;")

print("Inspecting cadastre.parquet schema...")
schema = conn.execute("DESCRIBE SELECT * FROM read_parquet('data/cadastre.parquet')").fetchall()
print("Schema:")
for col in schema:
    print(f"  {col[0]}: {col[1]}")

print("\nSample row:")
sample = conn.execute("SELECT * FROM read_parquet('data/cadastre.parquet') LIMIT 1").fetchone()
print(sample)

print("\nRow count:")
count = conn.execute("SELECT COUNT(*) FROM read_parquet('data/cadastre.parquet')").fetchone()[0]
print(f"{count:,} parcels")
