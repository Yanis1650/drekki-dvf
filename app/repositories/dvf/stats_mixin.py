"""Mixin des statistiques de prix au m2."""

from datetime import date
from decimal import Decimal

from app.repositories.dvf.mapping import appliquer_bornes

# Table enrichie par l'ETL : elle seule porte le drapeau `is_outlier`.
_REQUETE_ENRICHIE = """
    SELECT
        MIN(prix_m2)    as min_price,
        MAX(prix_m2)    as max_price,
        MEDIAN(prix_m2) as median_price,
        AVG(prix_m2)    as avg_price
    FROM france_foncier_test
    WHERE code_commune = ?
      AND prix_m2 IS NOT NULL AND prix_m2 > 0
      AND COALESCE(is_outlier, FALSE) = FALSE
"""

# Repli sur les mutations agregees : prix recalcule, outliers non ecartes.
_REQUETE_REPLI = """
    SELECT
        MIN(valeur_fonciere / surface_habitable_totale) as min_price,
        MAX(valeur_fonciere / surface_habitable_totale) as max_price,
        MEDIAN(valeur_fonciere / surface_habitable_totale) as median_price,
        AVG(valeur_fonciere / surface_habitable_totale) as avg_price
    FROM mutations_aggregated
    WHERE code_commune = ?
      AND surface_habitable_totale > 0
"""


class DvfStatsMixin:
    """Statistiques de prix, outliers exclus quand la base le permet."""

    async def get_price_stats(
        self,
        code_commune: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, Decimal]:
        """Get price statistics for a commune (outliers exclus).

        Utilise `france_foncier_test` pour beneficier du drapeau `is_outlier`
        calcule par l'ETL. Replie sur `mutations_aggregated` si la table
        enrichie n'existe pas (base non encore buildee) — auquel cas les
        valeurs aberrantes ne sont pas ecartees.
        """
        conn = self._get_connection()
        tables = {r[0] for r in conn.execute("SHOW TABLES").fetchall()}
        query = (
            _REQUETE_ENRICHIE if "france_foncier_test" in tables else _REQUETE_REPLI
        )

        params: list = [code_commune]
        query = appliquer_bornes(query, params, date_from, date_to)

        resultat = conn.execute(query, params).fetchone()

        return {
            "min_price_m2": Decimal(str(resultat[0])) if resultat[0] else Decimal("0"),
            "max_price_m2": Decimal(str(resultat[1])) if resultat[1] else Decimal("0"),
            "median_price_m2": Decimal(str(resultat[2])) if resultat[2] else Decimal("0"),
            "avg_price_m2": Decimal(str(resultat[3])) if resultat[3] else Decimal("0"),
        }
