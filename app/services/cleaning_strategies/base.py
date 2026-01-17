"""Base interface for cleaning strategies (Strategy Pattern)."""

from abc import ABC, abstractmethod

import polars as pl


class ICleaningStrategy(ABC):
    """Interface for DVF data cleaning strategies.

    Allows switching between methodologies (Mericskay vs Cerema)
    without modifying the analyzer service.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy identifier name."""
        ...

    @abstractmethod
    def filter_transactions(self, df: pl.LazyFrame) -> pl.LazyFrame:
        """Apply semantic filters to raw transactions.

        Args:
            df: Raw DVF LazyFrame

        Returns:
            Filtered LazyFrame
        """
        ...

    @abstractmethod
    def aggregate_mutations(self, df: pl.LazyFrame) -> pl.LazyFrame:
        """Group transactions by mutation ID.

        Args:
            df: Filtered transactions LazyFrame

        Returns:
            Aggregated mutations LazyFrame
        """
        ...

    @abstractmethod
    def calculate_price_per_m2(self, df: pl.LazyFrame) -> pl.LazyFrame:
        """Calculate price per m² according to methodology.

        Args:
            df: Aggregated mutations LazyFrame

        Returns:
            LazyFrame with prix_m2 column
        """
        ...

    def clean(self, df: pl.LazyFrame) -> pl.LazyFrame:
        """Full cleaning pipeline: filter → aggregate → calculate.

        Args:
            df: Raw DVF LazyFrame

        Returns:
            Fully processed LazyFrame
        """
        return (
            df
            .pipe(self.filter_transactions)
            .pipe(self.aggregate_mutations)
            .pipe(self.calculate_price_per_m2)
        )
