"""Enrichment ETL Pipeline.

Aggregates qualitative data (schools, transport, nuisances) per parcelle.
"""

import logging
from pathlib import Path

import duckdb
import polars as pl

logger = logging.getLogger(__name__)


class EnrichmentEtlPipeline:
    """ETL pipeline for qualitative enrichment data.

    Processes external data sources (schools, transport, nuisances)
    and computes scores per parcelle.
    """

    def __init__(
        self,
        duckdb_path: Path | str = "./data/foncier.duckdb",
    ) -> None:
        self._duckdb_path = Path(duckdb_path)

    def compute_schools_score(
        self,
        parcelles_df: pl.LazyFrame,
        schools_path: Path | str | None = None,
    ) -> pl.LazyFrame:
        """Compute schools proximity score (0-10).

        Higher score = more schools within 1km radius.
        """
        # Placeholder: return default score
        # TODO: Implement with actual schools data (BAN/SIRENE)
        return parcelles_df.with_columns(
            pl.lit(5.0).alias("schools_score")
        )

    def compute_transport_score(
        self,
        parcelles_df: pl.LazyFrame,
        transport_path: Path | str | None = None,
    ) -> pl.LazyFrame:
        """Compute public transport accessibility score (0-10).

        Based on proximity to metro/bus/tram stops.
        """
        # Placeholder: return default score
        # TODO: Implement with GTFS or OpenStreetMap data
        return parcelles_df.with_columns(
            pl.lit(5.0).alias("transport_score")
        )

    def compute_nuisances_score(
        self,
        parcelles_df: pl.LazyFrame,
        nuisances_path: Path | str | None = None,
    ) -> pl.LazyFrame:
        """Compute nuisances score (0-10).

        Inverted: higher score = fewer nuisances.
        Considers: noise pollution, industrial zones, highways.
        """
        # Placeholder: return default score
        # TODO: Implement with Plan de Prévention du Bruit
        return parcelles_df.with_columns(
            pl.lit(5.0).alias("nuisances_score")
        )

    def compute_green_spaces_score(
        self,
        parcelles_df: pl.LazyFrame,
        green_spaces_path: Path | str | None = None,
    ) -> pl.LazyFrame:
        """Compute green spaces accessibility score (0-10).

        Based on proximity to parks, forests, gardens.
        """
        # Placeholder: return default score
        # TODO: Implement with BD TOPO or OpenStreetMap
        return parcelles_df.with_columns(
            pl.lit(5.0).alias("green_spaces_score")
        )

    def run(self) -> int:
        """Execute enrichment ETL pipeline.

        Reads parcelles from DuckDB, computes scores,
        and saves enrichment_scores table.

        Returns:
            Number of parcelles enriched
        """
        logger.info("Starting enrichment ETL pipeline")

        conn = duckdb.connect(str(self._duckdb_path))

        try:
            # Check if parcelles table exists
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [t[0] for t in tables]

            if "parcelles" not in table_names:
                logger.warning("No parcelles table found, creating from mutations")
                # Extract unique parcelles from mutations
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS parcelles AS
                    SELECT DISTINCT
                        unnest(parcelles) as id_parcelle,
                        code_commune,
                        '' as prefixe,
                        '' as section,
                        '' as numero,
                        NULL as geometry,
                        NULL as surface_m2
                    FROM mutations_aggregated
                """)

            # Get parcelles as Polars DataFrame
            parcelles = conn.execute(
                "SELECT id_parcelle, code_commune FROM parcelles"
            ).pl()

            # Compute all scores
            enriched = (
                parcelles.lazy()
                .pipe(self.compute_schools_score)
                .pipe(self.compute_transport_score)
                .pipe(self.compute_nuisances_score)
                .pipe(self.compute_green_spaces_score)
                .collect()
            )

            # Save to DuckDB
            conn.execute("DROP TABLE IF EXISTS enrichment_scores")
            conn.register("enriched_df", enriched)
            conn.execute("""
                CREATE TABLE enrichment_scores AS
                SELECT
                    id_parcelle,
                    schools_score,
                    transport_score,
                    nuisances_score,
                    green_spaces_score
                FROM enriched_df
            """)

            count = len(enriched)
            logger.info(f"Enriched {count} parcelles")
            return count

        finally:
            conn.close()


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    duckdb_path = sys.argv[1] if len(sys.argv) > 1 else "./data/foncier.duckdb"

    pipeline = EnrichmentEtlPipeline(duckdb_path=duckdb_path)
    pipeline.run()
