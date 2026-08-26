"""OSM-based Enrichment ETL Pipeline.

Fetches POI from OpenStreetMap and loads into DuckDB.
Uses OSMnx for Overpass API integration.
"""

import logging
import sys
from pathlib import Path

import duckdb
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infrastructure.osm_client import OsmClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class OsmEnrichmentEtl:
    """ETL pipeline for OSM-based POI enrichment.

    Downloads POI from OpenStreetMap for communes with DVF mutations
    and stores them in DuckDB for scoring.
    """

    def __init__(self, duckdb_path: Path | str = "./data/foncier.duckdb") -> None:
        self._duckdb_path = Path(duckdb_path)
        self._osm_client = OsmClient()

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """Get DuckDB connection."""
        conn = duckdb.connect(str(self._duckdb_path))
        conn.execute("INSTALL spatial; LOAD spatial;")
        return conn

    def create_poi_table(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Create/update POI table schema."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS points_interet (
                id VARCHAR PRIMARY KEY,
                nom VARCHAR,
                type_poi VARCHAR,
                sous_type VARCHAR,
                longitude DOUBLE,
                latitude DOUBLE,
                code_commune VARCHAR,
                source VARCHAR DEFAULT 'osm'
            )
        """)
        logger.info("Table points_interet created/verified")

    def get_communes_to_process(
        self,
        conn: duckdb.DuckDBPyConnection,
        limit: int = 10,
    ) -> list[str]:
        """Get commune codes with most mutations to prioritize.

        Returns:
            List of commune codes ordered by mutation count
        """
        result = conn.execute("""
            SELECT code_commune, COUNT(*) as nb
            FROM mutations_aggregated
            WHERE code_commune IS NOT NULL
            GROUP BY code_commune
            ORDER BY nb DESC
            LIMIT ?
        """, [limit]).fetchall()

        return [r[0] for r in result]

    def get_commune_bbox(
        self,
        conn: duckdb.DuckDBPyConnection,
        code_commune: str,
    ) -> tuple[float, float, float, float] | None:
        """Get bounding box for a commune from mutations.

        Returns:
            (north, south, east, west) or None
        """
        result = conn.execute("""
            SELECT 
                MAX(latitude) as north,
                MIN(latitude) as south,
                MAX(longitude) as east,
                MIN(longitude) as west
            FROM mutations_aggregated
            WHERE code_commune = ?
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
        """, [code_commune]).fetchone()

        if result and result[0]:
            # Add margin (about 1km)
            margin = 0.01
            return (
                result[0] + margin,  # north
                result[1] - margin,  # south
                result[2] + margin,  # east
                result[3] - margin,  # west
            )
        return None

    def fetch_poi_for_commune(
        self,
        code_commune: str,
        bbox: tuple[float, float, float, float],
    ) -> pd.DataFrame:
        """Fetch OSM POI for a commune's bounding box.

        Args:
            code_commune: Commune code
            bbox: (north, south, east, west)

        Returns:
            DataFrame with POI data
        """
        north, south, east, west = bbox

        logger.info(f"Fetching OSM POI for commune {code_commune}...")

        # Fetch POI using OSMnx
        gdf = self._osm_client.fetch_poi_by_bbox(
            north=north,
            south=south,
            east=east,
            west=west,
        )

        if gdf.empty:
            logger.warning(f"No POI found for commune {code_commune}")
            return pd.DataFrame()

        # Convert to DataFrame with required columns
        df = pd.DataFrame({
            "id": [f"osm_{code_commune}_{i}" for i in range(len(gdf))],
            "nom": gdf["name"].fillna("").values if "name" in gdf.columns else [""] * len(gdf),
            "type_poi": gdf["category"].map(self._category_to_type_poi).values,
            "sous_type": gdf["sous_type"].values,
            "longitude": gdf["longitude"].values,
            "latitude": gdf["latitude"].values,
            "code_commune": code_commune,
            "source": "osm",
        })

        logger.info(f"  Fetched {len(df)} POI for {code_commune}")
        return df

    def load_poi_to_duckdb(
        self,
        conn: duckdb.DuckDBPyConnection,
        df: pd.DataFrame,
    ) -> int:
        """Load POI DataFrame into DuckDB.

        Returns:
            Number of POI inserted
        """
        if df.empty:
            return 0

        conn.register("poi_df", df)
        conn.execute("""
            INSERT OR REPLACE INTO points_interet
            SELECT * FROM poi_df
        """)

        return len(df)

    def run(
        self,
        communes_limit: int = 10,
        categories: list[str] | None = None,
    ) -> dict[str, int]:
        """Run full OSM enrichment ETL.

        Args:
            communes_limit: Number of top communes to process
            categories: POI categories to fetch

        Returns:
            Dict with counts per category
        """
        logger.info("Starting OSM Enrichment ETL")
        conn = self._get_connection()

        try:
            self.create_poi_table(conn)

            # Get top communes
            communes = self.get_communes_to_process(conn, limit=communes_limit)
            logger.info(f"Processing {len(communes)} communes")

            total_poi = 0

            for code_commune in communes:
                bbox = self.get_commune_bbox(conn, code_commune)
                if not bbox:
                    continue

                try:
                    df = self.fetch_poi_for_commune(code_commune, bbox)
                    count = self.load_poi_to_duckdb(conn, df)
                    total_poi += count
                except Exception as e:
                    logger.error(f"Failed to process {code_commune}: {e}")
                    continue

            # Create indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_poi_type 
                ON points_interet(type_poi)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_poi_commune 
                ON points_interet(code_commune)
            """)

            # Get final counts
            result = conn.execute("""
                SELECT type_poi, COUNT(*) as count
                FROM points_interet
                GROUP BY type_poi
            """).fetchall()

            counts = {r[0]: r[1] for r in result}

            logger.info(f"ETL Complete: {total_poi} total POI loaded")
            for poi_type, count in counts.items():
                logger.info(f"  - {poi_type}: {count}")

            return counts

        finally:
            conn.close()

    def _category_to_type_poi(self, category: str) -> str:
        """Map OSM category to type_poi."""
        mapping = {
            "education": "ecole",
            "transport": "transport",
            "transit": "transit",
            "nuisances": "nuisance",
            "commerce": "commerce",
            "environnement": "environnement",
        }
        return mapping.get(category, category)


def run_osm_enrichment():
    """Run OSM enrichment ETL from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="OSM Enrichment ETL")
    parser.add_argument("--db", default="./data/foncier.duckdb", help="DuckDB path")
    parser.add_argument("--communes", type=int, default=10, help="Number of communes")
    args = parser.parse_args()

    pipeline = OsmEnrichmentEtl(duckdb_path=args.db)
    pipeline.run(communes_limit=args.communes)


if __name__ == "__main__":
    run_osm_enrichment()
