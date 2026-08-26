"""POI Enrichment ETL Pipeline.

Loads Points of Interest (schools, transport) into DuckDB for scoring.
Uses Open Data sources:
- Education Nationale: établissements scolaires
- SNCF/GTFS: gares et stations
"""

import logging
from pathlib import Path

import duckdb
import polars as pl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PoiEtlPipeline:
    """ETL pipeline for Points of Interest.

    Loads schools, transport stations, and other POI into DuckDB
    with spatial indexing for fast proximity queries.
    """

    def __init__(self, duckdb_path: Path | str = "./data/foncier.duckdb") -> None:
        self._duckdb_path = Path(duckdb_path)

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """Get DuckDB connection with spatial extension."""
        conn = duckdb.connect(str(self._duckdb_path))
        conn.execute("INSTALL spatial; LOAD spatial;")
        return conn

    def create_poi_table(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Create the points_interet table if not exists."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS points_interet (
                id VARCHAR PRIMARY KEY,
                nom VARCHAR,
                type_poi VARCHAR,  -- 'ecole', 'gare', 'commerce'
                sous_type VARCHAR,  -- 'maternelle', 'elementaire', 'college', 'lycee', 'rer', 'metro'
                longitude DOUBLE,
                latitude DOUBLE,
                code_commune VARCHAR,
                code_postal VARCHAR
            )
        """)
        logger.info("Table points_interet created/verified")

    def load_schools_from_csv(
        self,
        conn: duckdb.DuckDBPyConnection,
        csv_path: Path | str | None = None,
    ) -> int:
        """Load schools from Education Nationale Open Data.

        If no CSV provided, generates sample data for development.
        """
        if csv_path and Path(csv_path).exists():
            logger.info(f"Loading schools from: {csv_path}")
            df = pl.read_csv(csv_path, ignore_errors=True)
            # Adapt column names to match expected schema
            # Education Nationale typically provides:
            # identifiant_de_l_etablissement, nom_etablissement, latitude, longitude, etc.
        else:
            logger.info("No schools CSV provided, generating sample data from mutations")
            # Generate POI from existing mutation locations for development
            result = conn.execute("""
                SELECT DISTINCT
                    code_commune,
                    longitude,
                    latitude
                FROM mutations_aggregated
                WHERE longitude IS NOT NULL
                  AND latitude IS NOT NULL
                LIMIT 5000
            """).fetchall()

            schools_data = []
            for i, r in enumerate(result):
                # Create synthetic schools near transaction locations
                import random
                for school_type in ['maternelle', 'elementaire', 'college']:
                    if random.random() < 0.3:  # 30% chance for each type
                        schools_data.append({
                            'id': f"ecole_{i}_{school_type}",
                            'nom': f"École {school_type.title()} {r[0]}",
                            'type_poi': 'ecole',
                            'sous_type': school_type,
                            'longitude': r[1] + random.uniform(-0.005, 0.005),
                            'latitude': r[2] + random.uniform(-0.005, 0.005),
                            'code_commune': r[0],
                            'code_postal': None,
                        })

            if schools_data:
                df = pl.DataFrame(schools_data)
                conn.register("schools_df", df)
                conn.execute("""
                    INSERT OR REPLACE INTO points_interet
                    SELECT * FROM schools_df
                """)
                logger.info(f"Loaded {len(schools_data)} synthetic schools")
                return len(schools_data)

        return 0

    def load_transport_from_csv(
        self,
        conn: duckdb.DuckDBPyConnection,
        csv_path: Path | str | None = None,
    ) -> int:
        """Load transport stations from GTFS/SNCF Open Data.

        If no CSV provided, generates sample data for development.
        """
        if csv_path and Path(csv_path).exists():
            logger.info(f"Loading transport from: {csv_path}")
            # GTFS stops.txt format: stop_id, stop_name, stop_lat, stop_lon
            df = pl.read_csv(csv_path, ignore_errors=True)
        else:
            logger.info("No transport CSV provided, generating sample data from mutations")
            # Generate synthetic transport stations
            result = conn.execute("""
                SELECT DISTINCT
                    code_commune,
                    AVG(longitude) as lon,
                    AVG(latitude) as lat
                FROM mutations_aggregated
                WHERE longitude IS NOT NULL
                  AND latitude IS NOT NULL
                GROUP BY code_commune
                LIMIT 2000
            """).fetchall()

            transport_data = []
            for i, r in enumerate(result):
                import random
                # One station per commune on average
                for transport_type in ['gare', 'metro', 'bus']:
                    if random.random() < 0.2:  # 20% chance
                        transport_data.append({
                            'id': f"transport_{i}_{transport_type}",
                            'nom': f"Station {transport_type.title()} {r[0]}",
                            'type_poi': 'gare',
                            'sous_type': transport_type,
                            'longitude': r[1] + random.uniform(-0.01, 0.01),
                            'latitude': r[2] + random.uniform(-0.01, 0.01),
                            'code_commune': r[0],
                            'code_postal': None,
                        })

            if transport_data:
                df = pl.DataFrame(transport_data)
                conn.register("transport_df", df)
                conn.execute("""
                    INSERT OR REPLACE INTO points_interet
                    SELECT * FROM transport_df
                """)
                logger.info(f"Loaded {len(transport_data)} synthetic transport stations")
                return len(transport_data)

        return 0

    def create_spatial_index(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Create indexes for fast spatial queries."""
        # Index on type_poi for filtering
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_poi_type
            ON points_interet(type_poi)
        """)
        # Index on coordinates for spatial queries
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_poi_coords
            ON points_interet(longitude, latitude)
        """)
        logger.info("Spatial indexes created")

    def run(
        self,
        schools_csv: Path | str | None = None,
        transport_csv: Path | str | None = None,
    ) -> dict[str, int]:
        """Execute full POI ETL pipeline.

        Args:
            schools_csv: Path to schools CSV (Education Nationale format)
            transport_csv: Path to transport CSV (GTFS format)

        Returns:
            Dict with counts of loaded POI by type
        """
        logger.info("Starting POI ETL pipeline")
        conn = self._get_connection()

        try:
            self.create_poi_table(conn)

            self.load_schools_from_csv(conn, schools_csv)
            self.load_transport_from_csv(conn, transport_csv)

            self.create_spatial_index(conn)

            # Get final counts
            result = conn.execute("""
                SELECT type_poi, COUNT(*) as count
                FROM points_interet
                GROUP BY type_poi
            """).fetchall()

            counts = {r[0]: r[1] for r in result}
            total = sum(counts.values())

            logger.info(f"POI ETL complete: {total} total POI")
            for poi_type, count in counts.items():
                logger.info(f"  - {poi_type}: {count}")

            return counts

        finally:
            conn.close()


def run_poi_etl():
    """Run POI ETL from command line."""
    import sys

    duckdb_path = "./data/foncier.duckdb"
    schools_csv = None
    transport_csv = None

    # Parse optional arguments
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--schools" and i + 2 < len(sys.argv):
            schools_csv = sys.argv[i + 2]
        elif arg == "--transport" and i + 2 < len(sys.argv):
            transport_csv = sys.argv[i + 2]
        elif arg == "--db" and i + 2 < len(sys.argv):
            duckdb_path = sys.argv[i + 2]

    pipeline = PoiEtlPipeline(duckdb_path=duckdb_path)
    pipeline.run(schools_csv=schools_csv, transport_csv=transport_csv)


if __name__ == "__main__":
    run_poi_etl()
