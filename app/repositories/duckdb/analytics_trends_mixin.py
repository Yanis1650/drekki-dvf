"""Requetes de tendances DVF pour le repository analytique."""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from math import cos, radians
from pathlib import Path
from typing import Any

import duckdb

from app.domain.analytics_models import YearlyTrend
from app.domain.dvf_methodology import (
    MIN_HABITABLE_SURFACE_M2,
    MIN_TRANSACTION_VALUE_EUR,
    SALE_NATURE,
)

logger = logging.getLogger(__name__)


class AnalyticsTrendsMixin:
    """Comportement de tendances, isole du parcours d'historique parcellaire."""

    _db_path: Path

    def _get_main_connection(self) -> duckdb.DuckDBPyConnection:
        raise NotImplementedError

    def _available_tables(self, conn: duckdb.DuckDBPyConnection) -> list[str]:
        raise NotImplementedError

    async def get_market_trends(
        self,
        code_commune: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
        radius_meters: int = 1000,
        years: int = 10,
    ) -> list[YearlyTrend]:
        """Retourne l'evolution annuelle des prix DVF pour une zone."""
        conn = self._get_main_connection()
        current_year = datetime.now().year
        start_year = current_year - years
        location_params: list[str] = []

        if code_commune:
            location_filter = "code_commune = ?"
            location_params.append(code_commune)
        elif lat is not None and lon is not None:
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

        tables = self._available_tables(conn)
        if "france_foncier_test" in tables:
            data_table = "france_foncier_test"
            extra_filter = "AND COALESCE(is_outlier, FALSE) = FALSE"
        elif "mutations_aggregated" in tables:
            data_table = "mutations_aggregated"
            extra_filter = ""
        else:
            logger.error("Ni france_foncier_test ni mutations_aggregated dans %s", self._db_path)
            return []

        query = f"""
            WITH filtered_data AS (
                SELECT YEAR(TRY_CAST(date_mutation AS DATE)) AS year, prix_m2
                FROM {data_table}
                WHERE {location_filter}
                  AND TRY_CAST(date_mutation AS DATE) >= DATE '{start_year}-01-01'
                  AND TRY_CAST(date_mutation AS DATE) <= DATE '{current_year}-12-31'
                  AND nature_mutation = ?
                  AND surface_habitable_totale > ?
                  AND valeur_fonciere > ?
                  AND prix_m2 IS NOT NULL AND prix_m2 > 0
                  {extra_filter}
            ),
            yearly_stats AS (
                SELECT year, AVG(prix_m2) AS avg_price_m2, COUNT(*) AS transaction_volume
                FROM filtered_data
                WHERE year IS NOT NULL
                GROUP BY year
            )
            SELECT year, avg_price_m2, transaction_volume,
                   LAG(avg_price_m2) OVER (ORDER BY year) AS prev_year_price
            FROM yearly_stats
            ORDER BY year ASC
        """
        try:
            results = conn.execute(
                query,
                [
                    *location_params,
                    SALE_NATURE,
                    float(MIN_HABITABLE_SURFACE_M2),
                    float(MIN_TRANSACTION_VALUE_EUR),
                ],
            ).fetchall()
        except duckdb.Error as error:
            logger.exception("get_market_trends a echoue (table=%s): %s", data_table, error)
            return []
        return self._to_yearly_trends(results)

    @staticmethod
    def _to_yearly_trends(results: list[tuple[Any, ...]]) -> list[YearlyTrend]:
        trends = []
        for year, avg_price, volume, previous_price in results:
            avg_price_decimal = Decimal(str(avg_price))
            yoy_change = None
            if previous_price is not None and previous_price > 0:
                previous_decimal = Decimal(str(previous_price))
                yoy_change = ((avg_price_decimal - previous_decimal) / previous_decimal) * 100
            trends.append(
                YearlyTrend(
                    year=year,
                    avg_price_m2=avg_price_decimal,
                    transaction_volume=volume,
                    yoy_change_pct=yoy_change,
                )
            )
        return trends
