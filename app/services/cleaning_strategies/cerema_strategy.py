"""CEREMA cleaning strategy (placeholder).

CEREMA uses different filtering criteria, notably:
- Different price thresholds
- Different surface calculations
- Additional filters for outliers

TODO: Implement based on CEREMA documentation.
"""

import polars as pl

from .base import ICleaningStrategy


class CeremaStrategy(ICleaningStrategy):
    """Strategy implementing CEREMA methodology.

    Placeholder implementation - to be completed based on
    CEREMA guidelines for DVF analysis.
    """

    @property
    def name(self) -> str:
        return "cerema"

    def filter_transactions(self, df: pl.LazyFrame) -> pl.LazyFrame:
        """Apply CEREMA semantic filters.

        TODO: Implement CEREMA-specific filters.
        Currently mirrors Mericskay as baseline.
        """
        return df.filter(
            (pl.col("nature_mutation") == "Vente")
            & (pl.col("valeur_fonciere") > 1000)
            & (pl.col("type_local").is_in(["Maison", "Appartement"]))
        )

    def aggregate_mutations(self, df: pl.LazyFrame) -> pl.LazyFrame:
        """Group by id_mutation.

        TODO: CEREMA may have different aggregation rules.
        """
        return df.group_by("id_mutation").agg(
            pl.first("date_mutation"),
            pl.first("nature_mutation"),
            pl.first("valeur_fonciere"),
            pl.first("code_commune"),
            pl.col("id_parcelle").unique().alias("parcelles"),
            pl.col("surface_reelle_bati").sum().alias("surface_habitable_totale"),
            pl.len().alias("nombre_locaux"),
        )

    def calculate_price_per_m2(self, df: pl.LazyFrame) -> pl.LazyFrame:
        """Calculate price/m².

        TODO: CEREMA uses different price computation.
        """
        return df.with_columns(
            pl.when(pl.col("surface_habitable_totale") > 0)
            .then(pl.col("valeur_fonciere") / pl.col("surface_habitable_totale"))
            .otherwise(None)
            .alias("prix_m2")
        ).filter(pl.col("surface_habitable_totale") > 0)
