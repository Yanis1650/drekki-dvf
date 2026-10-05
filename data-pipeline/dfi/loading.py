"""Ecriture des filiations dans DuckDB, par lots et avec ses index."""

import logging

import duckdb

logger = logging.getLogger(__name__)


class DfiLoadingMixin:
    """Chargement de `dfi_filiations`."""

    def load_to_duckdb(self, filiations: list[dict]) -> None:
        """Load filiation data into DuckDB.

        Creates table with composite index for fast lookups.

        Args:
            filiations: List of filiation records
        """
        if not filiations:
            logger.warning("No filiations to load")
            return

        owns_conn = self._conn is None
        if owns_conn:
            self._output_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Loading {len(filiations):,} filiations to DuckDB: {self._output_path}")
            conn = duckdb.connect(str(self._output_path))
        else:
            logger.info(f"Loading {len(filiations):,} filiations (connexion existante)")
            conn = self._conn

        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dfi_filiations (
                    code_departement VARCHAR(3),
                    code_commune VARCHAR(3),
                    prefixe VARCHAR(3),
                    id_dfi VARCHAR(7),
                    nature_dfi VARCHAR(1),
                    date_validation DATE,
                    numero_lot VARCHAR(5),
                    parcelle_mere VARCHAR(6),
                    parcelle_fille VARCHAR(6)
                )
            """)

            # Insert par lots pour eviter les limites memoire
            batch_size = 50_000
            for i in range(0, len(filiations), batch_size):
                batch = filiations[i : i + batch_size]
                rows = [
                    (
                        r["code_departement"],
                        r["code_commune"],
                        r["prefixe"],
                        r["id_dfi"],
                        r["nature_dfi"],
                        r["date_validation"],
                        r["numero_lot"],
                        r["parcelle_mere"],
                        r["parcelle_fille"],
                    )
                    for r in batch
                ]
                conn.executemany(
                    """INSERT INTO dfi_filiations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    rows,
                )
                if (i + batch_size) % 100_000 == 0 or i + batch_size >= len(filiations):
                    logger.info(f"  Inserted {min(i + batch_size, len(filiations)):,} rows")

            # Create composite indexes for fast lookups
            logger.info("Creating indexes...")

            # Index for finding mothers (query by daughter)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_dfi_fille
                ON dfi_filiations(code_commune, parcelle_fille)
            """)

            # Index for finding daughters (query by mother)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_dfi_mere
                ON dfi_filiations(code_commune, parcelle_mere)
            """)

            # Verify
            count = conn.execute("SELECT COUNT(*) FROM dfi_filiations").fetchone()[0]
            logger.info(f"✓ Loaded {count:,} filiation relationships to DuckDB")

        finally:
            # Ne jamais fermer une connexion prêtée par l'appelant.
            if owns_conn:
                conn.close()
