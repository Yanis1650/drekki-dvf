
import duckdb


def list_tables():
    try:
        conn = duckdb.connect("data/foncier.duckdb", read_only=True)
        print("Tables found:")
        print(conn.execute("SHOW TABLES").fetchall())
        conn.close()
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    list_tables()
