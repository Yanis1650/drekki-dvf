"""Briques du client OSM : catalogue de tags, normalisation."""

from app.infrastructure.osm.processing import OsmProcessingMixin
from app.infrastructure.osm.tags import OsmPoiConfig, OsmTag

__all__ = ["OsmPoiConfig", "OsmProcessingMixin", "OsmTag"]
