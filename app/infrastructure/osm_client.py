"""OSM Client for POI extraction.

Uses Overpass API via OSMnx to fetch Points of Interest.
"""

import logging
from dataclasses import dataclass

import geopandas as gpd
import osmnx as ox

logger = logging.getLogger(__name__)

# Configure OSMnx
ox.settings.use_cache = True
ox.settings.log_console = False
ox.settings.timeout = 180


@dataclass
class OsmTag:
    """OSM tag definition for POI extraction."""
    key: str
    value: str
    category: str  # ecole, transport, commerce, environnement
    weight: float = 1.0  # Importance weight for scoring


class OsmPoiConfig:
    """Configuration for POI extraction tags."""

    # Education POI
    EDUCATION_TAGS = [
        OsmTag("amenity", "school", "education", weight=1.0),
        OsmTag("amenity", "kindergarten", "education", weight=0.8),
        OsmTag("amenity", "university", "education", weight=1.2),
        OsmTag("amenity", "college", "education", weight=1.0),
        OsmTag("amenity", "library", "education", weight=0.5),
    ]

    # Transport POI
    TRANSPORT_TAGS = [
        OsmTag("public_transport", "station", "transport", weight=1.5),
        OsmTag("railway", "station", "transport", weight=1.5),
        OsmTag("railway", "halt", "transport", weight=1.0),
        OsmTag("highway", "bus_stop", "transport", weight=0.5),
        OsmTag("amenity", "bus_station", "transport", weight=1.0),
        OsmTag("railway", "tram_stop", "transport", weight=0.8),
        OsmTag("station", "subway", "transport", weight=1.2),
    ]

    # Commerce POI
    COMMERCE_TAGS = [
        OsmTag("shop", "supermarket", "commerce", weight=1.0),
        OsmTag("shop", "bakery", "commerce", weight=0.5),
        OsmTag("amenity", "marketplace", "commerce", weight=0.8),
        OsmTag("shop", "convenience", "commerce", weight=0.3),
    ]

    # Environment POI
    ENVIRONMENT_TAGS = [
        OsmTag("leisure", "park", "environnement", weight=1.0),
        OsmTag("landuse", "forest", "environnement", weight=0.8),
        OsmTag("natural", "water", "environnement", weight=0.5),
        OsmTag("leisure", "garden", "environnement", weight=0.7),
    ]

    @classmethod
    def get_all_tags(cls) -> list[OsmTag]:
        """Get all configured tags."""
        return (
            cls.EDUCATION_TAGS +
            cls.TRANSPORT_TAGS +
            cls.COMMERCE_TAGS +
            cls.ENVIRONMENT_TAGS
        )

    @classmethod
    def get_tags_by_category(cls, category: str) -> list[OsmTag]:
        """Get tags for a specific category."""
        mapping = {
            "education": cls.EDUCATION_TAGS,
            "transport": cls.TRANSPORT_TAGS,
            "commerce": cls.COMMERCE_TAGS,
            "environnement": cls.ENVIRONMENT_TAGS,
        }
        return mapping.get(category, [])

    @classmethod
    def to_osm_tags_dict(cls, tags: list[OsmTag]) -> dict[str, list[str]]:
        """Convert to OSMnx tags dict format."""
        result: dict[str, list[str]] = {}
        for tag in tags:
            if tag.key not in result:
                result[tag.key] = []
            result[tag.key].append(tag.value)
        return result


class OsmClient:
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
            categories = ["education", "transport", "commerce", "environnement"]

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
            categories = ["education", "transport", "commerce", "environnement"]

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
            categories = ["education", "transport", "commerce", "environnement"]

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

    def _process_gdf(
        self,
        gdf: gpd.GeoDataFrame,
        category: str,
        tags: list[OsmTag],
    ) -> gpd.GeoDataFrame:
        """Process and standardize GeoDataFrame columns."""
        import pandas as pd

        # Get centroid for polygons
        gdf = gdf.copy()
        gdf["geometry"] = gdf["geometry"].centroid

        # Extract coordinates
        gdf["longitude"] = gdf["geometry"].x
        gdf["latitude"] = gdf["geometry"].y

        # Determine sub-type from tags
        def get_subtype(row: pd.Series) -> str:
            for tag in tags:
                if tag.key in row.index and row[tag.key] == tag.value:
                    return tag.value
            return "unknown"

        gdf["category"] = category
        gdf["sous_type"] = gdf.apply(get_subtype, axis=1)

        # Get name if available
        if "name" not in gdf.columns:
            gdf["name"] = None

        # Select relevant columns
        cols = ["name", "category", "sous_type", "longitude", "latitude", "geometry"]
        existing_cols = [c for c in cols if c in gdf.columns]

        return gdf[existing_cols].copy()
