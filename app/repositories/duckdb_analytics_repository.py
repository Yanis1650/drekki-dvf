"""DuckDB Analytics Repository.

Dedicated repository for market trends and analytics queries.
Separated from main repository to maintain 400-line limit (SRP).
"""

from datetime import datetime
from decimal import Decimal
from math import cos, radians
from pathlib import Path

import duckdb

from app.domain.analytics_models import YearlyTrend


class DuckDBAnalyticsRepository:
    """Analytics repository for market trends analysis.
    
    Handles complex temporal and spatial aggregations for market insights.
    Uses DuckDB's analytical functions for efficient yearly grouping.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._conn: duckdb.DuckDBPyConnection | None = None

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """Lazy connection initialization with spatial extension."""
        if self._conn is None:
            self._conn = duckdb.connect(str(self._db_path), read_only=True)
            self._conn.execute("INSTALL spatial; LOAD spatial;")
        return self._conn

    async def get_market_trends(
        self,
        code_commune: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
        radius_meters: int = 1000,
        years: int = 10,
    ) -> list[YearlyTrend]:
        """Get market trends over time for a location.
        
        Strategy:
        1. Filter by commune OR radius around coordinates
        2. Apply Mericskay methodology filters
        3. Group by year and calculate metrics
        4. Calculate YoY percentage changes
        
        Args:
            code_commune: INSEE commune code (e.g., "35238" for Rennes)
            lat: Latitude for radius search (WGS84)
            lon: Longitude for radius search (WGS84)
            radius_meters: Search radius in meters
            years: Number of years to analyze (from current year backwards)
        
        Returns:
            List of YearlyTrend objects ordered by year ascending
        """
        conn = self._get_connection()

        # Determine current year and start year
        current_year = datetime.now().year
        start_year = current_year - years

        # Build WHERE clause based on location type
        if code_commune:
            location_filter = f"code_commune = '{code_commune}'"
        elif lat is not None and lon is not None:
            # Calculate bounding box for performance
            lat_delta = radius_meters / 111000
            lon_delta = radius_meters / (111000 * abs(cos(radians(lat))))

            location_filter = f"""
                longitude BETWEEN {lon - lon_delta} AND {lon + lon_delta}
                AND latitude BETWEEN {lat - lat_delta} AND {lat + lat_delta}
                AND (
                    6371000 * ACOS(
                        LEAST(1.0, GREATEST(-1.0,
                            COS(RADIANS({lat})) * COS(RADIANS(latitude)) *
                            COS(RADIANS(longitude) - RADIANS({lon})) +
                            SIN(RADIANS({lat})) * SIN(RADIANS(latitude))
                        ))
                    ) <= {radius_meters}
                )
            """
        else:
            raise ValueError("Must provide either code_commune or (lat, lon)")

        # Query with Mericskay filters and yearly aggregation
        query = f"""
            WITH filtered_data AS (
                SELECT 
                    YEAR(TRY_CAST(date_mutation AS DATE)) as year,
                    prix_m2,
                    valeur_fonciere,
                    surface_habitable_totale
                FROM france_foncier_test
                WHERE {location_filter}
                  AND TRY_CAST(date_mutation AS DATE) >= DATE '{start_year}-01-01'
                  AND TRY_CAST(date_mutation AS DATE) <= DATE '{current_year}-12-31'
                  AND nature_mutation = 'Vente'
                  AND surface_habitable_totale > 9
                  AND valeur_fonciere > 2000
                  AND prix_m2 IS NOT NULL
                  AND prix_m2 > 0
            ),
            yearly_stats AS (
                SELECT 
                    year,
                    AVG(prix_m2) as avg_price_m2,
                    COUNT(*) as transaction_volume
                FROM filtered_data
                WHERE year IS NOT NULL
                GROUP BY year
                ORDER BY year ASC
            )
            SELECT 
                year,
                avg_price_m2,
                transaction_volume,
                LAG(avg_price_m2) OVER (ORDER BY year) as prev_year_price
            FROM yearly_stats
            ORDER BY year ASC
        """

        try:
            results = conn.execute(query).fetchall()
        except Exception as e:
            print(f"ERROR: get_market_trends query failed: {e}")
            return []

        # Convert to domain models and calculate YoY changes
        trends = []
        for r in results:
            year = r[0]
            avg_price = Decimal(str(r[1]))
            volume = r[2]
            prev_price = r[3]

            # Calculate YoY percentage change
            yoy_change = None
            if prev_price is not None and prev_price > 0:
                prev_price_decimal = Decimal(str(prev_price))
                yoy_change = ((avg_price - prev_price_decimal) / prev_price_decimal) * 100

            trends.append(YearlyTrend(
                year=year,
                avg_price_m2=avg_price,
                transaction_volume=volume,
                yoy_change_pct=yoy_change,
            ))

        return trends

    async def get_parcel_history(
        self,
        parcel_id: str,
        limit: int = 100,
    ) -> list[dict]:
        """Get transaction history for a specific parcel.
        
        Used for MapLibre tooltips to show historical sales.
        
        Args:
            parcel_id: Cadastral parcel ID (14 chars: commune(5) + prefixe(3) + section(2) + numero(4))
            limit: Maximum number of transactions to return
        
        Returns:
            List of transaction dicts with date, price, and price_m2
        """
        conn = self._get_connection()

        # DEBUG: Log input parcel ID
        print(f"🔍 [REPO] get_parcel_history called with parcel_id: '{parcel_id}'")
        print(f"🔍 [REPO] parcel_id length: {len(parcel_id)}")

        # Parcel ID structure (14 chars):
        # - code_commune: 5 chars (e.g., "35238")
        # - prefixe: 3 chars (e.g., "000")
        # - section: 2 chars (e.g., "AO")
        # - numero: 4 chars with leading zeros (e.g., "0141")
        #
        # DVF may store the numero WITHOUT leading zeros (e.g., "141" instead of "0141")
        # So we need to match both formats

        if len(parcel_id) == 14:
            # Extract components
            base_id = parcel_id[:10]  # commune + prefixe + section
            numero_padded = parcel_id[10:]  # 4-char numero with leading zeros
            numero_stripped = numero_padded.lstrip('0') or '0'  # Remove leading zeros

            # Build alternative IDs that DVF might use
            alt_id_short = base_id + numero_stripped  # e.g., "35238000AO141"

            query = """
                SELECT 
                    date_mutation,
                    valeur_fonciere,
                    prix_m2,
                    surface_habitable_totale,
                    cadastre_parcelle_id
                FROM france_foncier_test
                WHERE cadastre_parcelle_id IN (?, ?)
                  AND valeur_fonciere > 0
                ORDER BY date_mutation DESC
                LIMIT ?
            """
            params = [parcel_id, alt_id_short, limit]

            # DEBUG: Log the exact match parameters
            print(f"🔍 [REPO] Searching for exact IDs: '{parcel_id}' OR '{alt_id_short}'")
        else:
            # For non-14-char IDs, do exact match only
            query = """
                SELECT 
                    date_mutation,
                    valeur_fonciere,
                    prix_m2,
                    surface_habitable_totale,
                    cadastre_parcelle_id
                FROM france_foncier_test
                WHERE cadastre_parcelle_id = ?
                  AND valeur_fonciere > 0
                ORDER BY date_mutation DESC
                LIMIT ?
            """
            params = [parcel_id, limit]
            print(f"🔍 [REPO] Searching for exact ID only: '{parcel_id}'")

        try:
            results = conn.execute(query, params).fetchall()

            # DEBUG: Log results
            print(f"🔍 [REPO] Found {len(results)} transactions")
            if results:
                unique_ids = set(r[4] for r in results if r[4])
                print(f"🔍 [REPO] Unique cadastre_parcelle_ids in results: {unique_ids}")

        except Exception as e:
            print(f"ERROR: get_parcel_history failed: {e}")
            return []

        history = []
        for r in results:
            mutation_date = r[0]
            if isinstance(mutation_date, str):
                mutation_date = datetime.strptime(mutation_date, "%Y-%m-%d").date()

            history.append({
                "date": str(mutation_date),
                "price": float(r[1]),
                "price_m2": float(r[2]) if r[2] else None,
                "surface": float(r[3]) if r[3] else None,
            })

        return history

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
