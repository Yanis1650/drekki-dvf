"""Normalisation des GeoDataFrame renvoyes par OSMnx.

Note connue : le centroide est calcule sur des coordonnees geographiques
(EPSG:4326), donc comme si la Terre etait plane. L'ecart est negligeable a
l'echelle d'un POI, mais geopandas emet un avertissement a chaque appel.
"""

import geopandas as gpd
import pandas as pd

from app.infrastructure.osm.tags import OsmTag


class OsmProcessingMixin:
    """Mise en forme des POI bruts."""

    def _process_gdf(
        self,
        gdf: gpd.GeoDataFrame,
        category: str,
        tags: list[OsmTag],
    ) -> gpd.GeoDataFrame:
        """Process and standardize GeoDataFrame columns."""

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
