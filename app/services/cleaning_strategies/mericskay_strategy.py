"""Mericskay & Demoraes 2021 cleaning strategy.

Reference: Mericskay & Demoraes (2021) - Analyse des données DVF.
Filtrage sémantique + regroupement par mutation + prix m² habitable.
"""

import polars as pl

from .base import ICleaningStrategy


class MericskayStrategy(ICleaningStrategy):
    """Strategy implementing Mericskay & Demoraes 2021 methodology.

    Filters:
    - nature_mutation = 'Vente'
    - valeur_fonciere > 1000€
    - surface_reelle_bati > 9m² (for habitable locals)

    Aggregation:
    - GroupBy id_mutation to handle 1-N cardinality

    Price/m²:
    - valeur_fonciere / sum(surface habitable Type 1 & 2)
    """

    @property
    def name(self) -> str:
        return "mericskay_2021"

    def filter_transactions(self, df: pl.LazyFrame) -> pl.LazyFrame:
        """Apply Mericskay semantic filters."""
        return df.filter(
            (pl.col("nature_mutation") == "Vente")
            & (pl.col("valeur_fonciere") > 1000)
            & (
                # Keep habitable locals (Type 1: Maison, Type 2: Appartement)
                (pl.col("type_local").is_in(["Maison", "Appartement"]))
                | (pl.col("type_local").is_null())  # Keep for aggregation
            )
        )

    def aggregate_mutations(self, df: pl.LazyFrame) -> pl.LazyFrame:
        """Group by id_mutation to handle multi-local transactions."""
        return df.group_by("id_mutation").agg(
            pl.first("date_mutation"),
            pl.first("nature_mutation"),
            pl.first("valeur_fonciere"),
            pl.first("code_commune"),
            pl.col("id_parcelle").unique().alias("parcelles"),
            # Sum only habitable surface (Type 1 & 2)
            pl.col("surface_reelle_bati")
            .filter(pl.col("type_local").is_in(["Maison", "Appartement"]))
            .sum()
            .alias("surface_habitable_totale"),
            pl.len().alias("nombre_locaux"),
        )

    def calculate_price_per_m2(self, df: pl.LazyFrame) -> pl.LazyFrame:
        """Calculate price/m² using habitable surface only."""
        return df.with_columns(
            pl.when(pl.col("surface_habitable_totale") > 9)
            .then(pl.col("valeur_fonciere") / pl.col("surface_habitable_totale"))
            .otherwise(None)
            .alias("prix_m2")
        ).filter(
            # Final filter: min surface 9m² per Mericskay
            pl.col("surface_habitable_totale") > 9
        )
