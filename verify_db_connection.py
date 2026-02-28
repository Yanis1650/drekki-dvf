"""Script utilitaire pour tester la connexion PostGIS (dev local).

Usage:
    export POSTGIS_USER=foncier POSTGIS_PASSWORD=xxx POSTGIS_DB=foncier_express
    python verify_db_connection.py
"""

import os

import psycopg


def test_auth(user: str, password: str, db: str, host: str = "127.0.0.1", port: int = 5433) -> bool:
    """Vérifie la connexion PostGIS."""
    try:
        conn = psycopg.connect(
            user=user,
            password=password,
            dbname=db,
            host=host,
            port=port,
        )
        print(f"SUCCESS: connexion à {db} établie")
        conn.close()
        return True
    except Exception as e:
        print(f"FAIL: {e}")
        return False


def main() -> None:
    user = os.getenv("POSTGIS_USER", "foncier")
    password = os.getenv("POSTGIS_PASSWORD")
    db = os.getenv("POSTGIS_DB", "foncier_express")
    host = os.getenv("POSTGIS_HOST", "127.0.0.1")
    port = int(os.getenv("POSTGIS_PORT", "5433"))

    if not password:
        print("ERREUR: Définir POSTGIS_PASSWORD (ex: export POSTGIS_PASSWORD=xxx)")
        return

    test_auth(user, password, db, host, port)


if __name__ == "__main__":
    main()
