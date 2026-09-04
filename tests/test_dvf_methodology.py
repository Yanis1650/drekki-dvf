"""Contrat partage de la methode DVF appliquee aux donnees servies."""

from datetime import datetime
from decimal import Decimal

import duckdb
import pytest

from app.domain.dvf_methodology import (
    HABITABLE_LOCAL_TYPES,
    MIN_HABITABLE_SURFACE_M2,
    MIN_TRANSACTION_VALUE_EUR,
    SALE_NATURE,
)
from app.repositories.duckdb_analytics_repository import DuckDBAnalyticsRepository


def test_canonical_mericskay_rules_are_explicit():
    assert SALE_NATURE == "Vente"
    assert MIN_TRANSACTION_VALUE_EUR == Decimal("1000")
    assert MIN_HABITABLE_SURFACE_M2 == Decimal("9")
    assert HABITABLE_LOCAL_TYPES == ("Maison", "Appartement")


@pytest.mark.asyncio
async def test_market_trends_uses_canonical_threshold_and_bound_commune_parameter(tmp_path):
    database = tmp_path / "analytics.duckdb"
    conn = duckdb.connect(str(database))
    current_year = datetime.now().year
    conn.execute(
        """
        CREATE TABLE mutations_aggregated (
            code_commune VARCHAR, date_mutation VARCHAR, nature_mutation VARCHAR,
            valeur_fonciere DOUBLE, surface_habitable_totale DOUBLE, prix_m2 DOUBLE
        )
        """
    )
    conn.execute(
        """
        INSERT INTO mutations_aggregated VALUES
        ('35238', ?, 'Vente', 1500, 10, 150),
        ('35238', ?, 'Vente', 1000, 10, 100),
        ('99999', ?, 'Vente', 200000, 100, 2000)
        """,
        [f"{current_year}-01-15", f"{current_year}-02-15", f"{current_year}-03-15"],
    )

    repository = DuckDBAnalyticsRepository(database)
    repository._get_main_connection = lambda: conn  # type: ignore[method-assign]

    trends = await repository.get_market_trends(code_commune="35238", years=1)
    injection = await repository.get_market_trends(code_commune="35238' OR 1=1 --", years=1)

    assert len(trends) == 1
    assert trends[0].transaction_volume == 1
    assert trends[0].avg_price_m2 == Decimal("150")
    assert injection == []
    conn.close()
