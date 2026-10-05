"""Briques du rapport parcelle, composees dans `ParcelReportService`."""

from app.services.report_parcel.aggregate import ReportAggregateMixin
from app.services.report_parcel.formatting import ReportFormattingMixin

__all__ = ["ReportAggregateMixin", "ReportFormattingMixin"]
