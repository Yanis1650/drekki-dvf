"""Mesures et controles portant sur le contenu d'une base DVF candidate."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dvf_quality_report import _check  # noqa: E402

from app.domain.dvf_methodology import (  # noqa: E402
    MIN_HABITABLE_SURFACE_M2,
    MIN_TRANSACTION_VALUE_EUR,
    SALE_NATURE,
)

TABLE = "mutations_aggregated"
REQUIRED_COLUMNS = {
    "id_mutation",
    "date_mutation",
    "nature_mutation",
    "valeur_fonciere",
    "code_commune",
    "parcelles",
    "surface_habitable_totale",
    "nombre_locaux",
    "longitude",
    "latitude",
    "type_local",
    "prix_m2",
}


def collect_metrics(conn: Any, report: dict[str, Any]) -> int:
    """Remplit `report["metrics"]` et ses controles ; rend le nombre de mutations."""
    validation_params = [SALE_NATURE, MIN_TRANSACTION_VALUE_EUR, MIN_HABITABLE_SURFACE_M2]
    (
        count,
        duplicate_count,
        incomplete_count,
        invalid_values,
        invalid_dates,
        invalid_prices,
        missing_coordinates,
        invalid_coordinates,
        missing_parcel_links,
    ) = conn.execute(
        """
        SELECT
            COUNT(*),
            COUNT(*) - COUNT(DISTINCT id_mutation),
            COUNT(*) FILTER (WHERE id_mutation IS NULL OR TRIM(id_mutation) = ''
                OR date_mutation IS NULL OR nature_mutation IS NULL OR TRIM(nature_mutation) = ''
                OR valeur_fonciere IS NULL OR code_commune IS NULL OR TRIM(code_commune) = ''
                OR parcelles IS NULL OR ARRAY_LENGTH(parcelles) = 0
                OR surface_habitable_totale IS NULL OR nombre_locaux IS NULL
                OR longitude IS NULL OR latitude IS NULL
                OR type_local IS NULL OR TRIM(type_local) = ''
                OR prix_m2 IS NULL),
            COUNT(*) FILTER (WHERE nature_mutation IS NULL OR nature_mutation <> ?
                OR valeur_fonciere IS NULL OR valeur_fonciere <= ?
                OR surface_habitable_totale IS NULL OR surface_habitable_totale <= ?),
            COUNT(*) FILTER (WHERE TRY_CAST(date_mutation AS DATE) IS NULL),
            COUNT(*) FILTER (WHERE prix_m2 IS NULL OR prix_m2 <= 0),
            COUNT(*) FILTER (WHERE longitude IS NULL OR latitude IS NULL),
            COUNT(*) FILTER (WHERE longitude IS NOT NULL AND latitude IS NOT NULL
                AND (longitude < -180 OR longitude > 180 OR latitude < -90 OR latitude > 90)),
            COUNT(*) FILTER (WHERE parcelles IS NULL OR ARRAY_LENGTH(parcelles) = 0)
        FROM mutations_aggregated
        """,
        validation_params,
    ).fetchone()
    date_range = conn.execute(
        """
        SELECT MIN(TRY_CAST(date_mutation AS DATE)), MAX(TRY_CAST(date_mutation AS DATE))
        FROM mutations_aggregated
        """
    ).fetchone()
    yearly_counts = {
        str(year): int(year_count)
        for year, year_count in conn.execute(
            """
            SELECT YEAR(TRY_CAST(date_mutation AS DATE)), COUNT(*)
            FROM mutations_aggregated
            GROUP BY 1
            ORDER BY 1
            """
        ).fetchall()
        if year is not None
    }
    price_by_type = {
        local_type: {
            "mutation_count": int(type_count),
            "median_prix_m2": float(median_price) if median_price is not None else None,
        }
        for local_type, type_count, median_price in conn.execute(
            """
            SELECT type_local, COUNT(*), QUANTILE_CONT(prix_m2, 0.5)
            FROM mutations_aggregated
            GROUP BY 1
            ORDER BY 1
            """
        ).fetchall()
    }
    report["metrics"] = {
        "mutation_count": count,
        "date_range": {
            "min": str(date_range[0]) if date_range[0] else None,
            "max": str(date_range[1]) if date_range[1] else None,
        },
        "commune_count": conn.execute(
            "SELECT COUNT(DISTINCT code_commune) FROM mutations_aggregated"
        ).fetchone()[0],
        "yearly_mutation_counts": yearly_counts,
        "geolocation": {
            "complete": count - missing_coordinates,
            "rate": round((count - missing_coordinates) / count, 4) if count else 0.0,
        },
        "parcel_links": {
            "complete": count - missing_parcel_links,
            "rate": round((count - missing_parcel_links) / count, 4) if count else 0.0,
        },
        "price_per_sqm_by_local_type": price_by_type,
    }
    report["checks"].extend(
        [
            _check("non_empty_dataset", count > 0, count, "> 0 mutations"),
            _check("unique_mutation_ids", duplicate_count == 0, duplicate_count, "0 duplicates"),
            _check("complete_required_values", incomplete_count == 0, incomplete_count, "0 missing values"),
            _check(
                "valid_transaction_values",
                invalid_values == 0,
                invalid_values,
                f"{SALE_NATURE}, value > {MIN_TRANSACTION_VALUE_EUR}, surface > {MIN_HABITABLE_SURFACE_M2}",
            ),
            _check("valid_mutation_dates", invalid_dates == 0, invalid_dates, "0 invalid dates"),
            _check("valid_prices_per_sqm", invalid_prices == 0, invalid_prices, "0 null or non-positive prices"),
            _check(
                "valid_geolocation_coordinates",
                invalid_coordinates == 0,
                invalid_coordinates,
                "0 coordinates outside longitude [-180, 180] or latitude [-90, 90]",
            ),
        ]
    )
    return count
