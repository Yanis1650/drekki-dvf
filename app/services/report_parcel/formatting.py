"""Filtres de formatage exposes aux gabarits Jinja.

Ils sont enregistres sous les noms `format_currency` et `format_date`, que
les gabarits appellent tels quels : une faute de frappe cote enregistrement
ne se verrait qu'a la generation du PDF.
"""

from datetime import datetime
from decimal import Decimal


class ReportFormattingMixin:
    """Mise en forme francaise des montants et des dates."""

    @staticmethod
    def _format_currency(value: float | Decimal | None) -> str:
        """Format value as French currency."""
        if value is None:
            return "N/A"
        return f"{float(value):,.0f} €".replace(",", " ")

    @staticmethod
    def _format_date(date_str: str | None) -> str:
        """Format date string to French format."""
        if not date_str:
            return "N/A"
        try:
            dt = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
            return dt.strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            return str(date_str)
