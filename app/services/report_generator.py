"""Generation du rapport PDF de faisabilite fonciere.

Les figures vivent dans `report/charts.py`, la mise en page dans
`report/pdf.py`, et les couleurs dans `report/palette.py`. Cette classe
ne fait que les composer.
"""

import logging

from app.services.report import ReportChartsMixin, ReportPdfMixin

logger = logging.getLogger(__name__)

__all__ = ["ReportGenerator"]


class ReportGenerator(ReportChartsMixin, ReportPdfMixin):
    """Produit les figures puis le document PDF d'un rapport parcelle."""
