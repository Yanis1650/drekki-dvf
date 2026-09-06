"""Paquet POI — mixins composes dans `PoiRepository`."""

from app.repositories.poi.enrichment_mixin import PoiEnrichmentMixin
from app.repositories.poi.spatial_mixin import PoiSpatialMixin

__all__ = ["PoiEnrichmentMixin", "PoiSpatialMixin"]
