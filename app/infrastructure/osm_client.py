"""OSM Client for POI extraction.

Uses Overpass API via OSMnx to fetch Points of Interest.

Le catalogue de tags vit dans `osm/tags.py`, la normalisation des resultats
dans `osm/processing.py`. Ce module ne porte plus que les trois appels reseau.
"""

import logging

import geopandas as gpd
import osmnx as ox
import pandas as pd

from app.infrastructure.osm import OsmPoiConfig, OsmProcessingMixin, OsmTag

logger = logging.getLogger(__name__)

# Configure OSMnx
ox.settings.use_cache = True
ox.settings.log_console = False
ox.settings.timeout = 180

__all__ = ["OsmClient", "OsmPoiConfig", "OsmTag"]


class OsmClient(OsmProcessingMixin):
    """Client for fetching OSM POI data."""

    def __init__(self) -> None:
        self._config = OsmPoiConfig()

    def fetch_poi_by_place(
        self,
        place_name: str,
        categories: list[str] | None = None,
    ) -> gpd.GeoDataFrame:
        """Fetch POI for a place by name.

        Args:
            place_name: OSM place name (e.g., "Toulouse, France")
            categories: List of categories to fetch (education, transport, etc.)

        Returns:
            GeoDataFrame with all POI
        """
        if categories is None:
            categories = ["education", "transport", "transit", "nuisances", "commerce", "environnement"]

        all_gdf = []

        for category in categories:
            tags = self._config.get_tags_by_category(category)
            if not tags:
                continue

            tags_dict = self._config.to_osm_tags_dict(tags)

            try:
                logger.info(f"Fetching {category} POI for {place_name}...")
                gdf = ox.features_from_place(place_name, tags=tags_dict)

                if len(gdf) > 0:
                    gdf = self._process_gdf(gdf, category, tags)
                    all_gdf.append(gdf)
                    logger.info(f"  Found {len(gdf)} {category} POI")

            except Exception as e:
                logger.warning(f"Failed to fetch {category} for {place_name}: {e}")
                continue

        if not all_gdf:
            return gpd.GeoDataFrame()

        return gpd.GeoDataFrame(pd.concat(all_gdf, ignore_index=True))

    def fetch_poi_by_bbox(
        self,
        north: float,
        south: float,
        east: float,
        west: float,
        categories: list[str] | None = None,
    ) -> gpd.GeoDataFrame:
        """Fetch POI within a bounding box.

        Args:
            north, south, east, west: Bounding box coordinates (WGS84)
            categories: List of categories to fetch

        Returns:
            GeoDataFrame with all POI
        """
        if categories is None:
            categories = ["education", "transport", "transit", "nuisances", "commerce", "environnement"]

        all_gdf = []

        for category in categories:
            tags = self._config.get_tags_by_category(category)
            if not tags:
                continue

            tags_dict = self._config.to_osm_tags_dict(tags)

            try:
                logger.info(f"Fetching {category} POI for bbox...")
                gdf = ox.features_from_bbox(
                    bbox=(west, south, east, north),
                    tags=tags_dict,
                )

                if len(gdf) > 0:
                    gdf = self._process_gdf(gdf, category, tags)
                    all_gdf.append(gdf)
                    logger.info(f"  Found {len(gdf)} {category} POI")

            except Exception as e:
                logger.warning(f"Failed to fetch {category}: {e}")
                continue

        if not all_gdf:
            return gpd.GeoDataFrame()

        import pandas as pd
        return gpd.GeoDataFrame(pd.concat(all_gdf, ignore_index=True))

    def fetch_poi_around_point(
        self,
        lat: float,
        lon: float,
        dist_meters: int = 2000,
        categories: list[str] | None = None,
    ) -> gpd.GeoDataFrame:
        """Fetch POI within a distance from a point.

        Args:
            lat, lon: Center point coordinates (WGS84)
            dist_meters: Search radius in meters
            categories: List of categories to fetch

        Returns:
            GeoDataFrame with all POI
        """
        if categories is None:
            categories = ["education", "transport", "transit", "nuisances", "commerce", "environnement"]

        all_gdf = []

        for category in categories:
            tags = self._config.get_tags_by_category(category)
            if not tags:
                continue

            tags_dict = self._config.to_osm_tags_dict(tags)

            try:
                gdf = ox.features_from_point(
                    center_point=(lat, lon),
                    dist=dist_meters,
                    tags=tags_dict,
                )

                if len(gdf) > 0:
                    gdf = self._process_gdf(gdf, category, tags)
                    all_gdf.append(gdf)

            except Exception as e:
                logger.debug(f"No {category} POI found: {e}")
                continue

        if not all_gdf:
            return gpd.GeoDataFrame()

        import pandas as pd
        return gpd.GeoDataFrame(pd.concat(all_gdf, ignore_index=True))
