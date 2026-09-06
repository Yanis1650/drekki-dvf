"""Briques du rapport PDF, composees dans `ReportGenerator`."""

from app.services.report.charts import ReportChartsMixin
from app.services.report.pdf import ReportPdfMixin

__all__ = ["ReportChartsMixin", "ReportPdfMixin"]
