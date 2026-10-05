"""Catalogue des POI recherches sur OpenStreetMap.

Ce que ce fichier declare determine ce que l'enrichissement va chercher :
une categorie qui disparait fait tomber son score a zero partout, sans
qu'aucune erreur ne soit levee. `tests/test_osm_client.py` verifie que les
six categories restent servies.

Transit et transport sont deliberement distincts : le premier suit une
cloche TOD centree sur 600 m, le second une decroissance simple.
"""

from dataclasses import dataclass


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

    # Transport POI — bus, vélo, mobilités douces (décroissance exponentielle)
    TRANSPORT_TAGS = [
        OsmTag("highway", "bus_stop", "transport", weight=0.5),
        OsmTag("amenity", "bus_station", "transport", weight=1.0),
        OsmTag("amenity", "bicycle_rental", "transport", weight=0.4),
        OsmTag("amenity", "bicycle_parking", "transport", weight=0.3),
    ]

    # Transit POI — gares ferroviaires / métro / tram (décroissance en cloche TOD)
    # Effet non-monotone : zone optimale 400-800m, pénalisé si trop proche (bruit).
    TRANSIT_TAGS = [
        OsmTag("railway", "station", "transit", weight=1.5),
        OsmTag("railway", "halt", "transit", weight=1.0),
        OsmTag("railway", "tram_stop", "transit", weight=0.8),
        OsmTag("public_transport", "stop_position", "transit", weight=1.0),
    ]

    # Nuisances POI — facteurs négatifs de valeur (bruit, pollution, industrie)
    NUISANCES_TAGS = [
        OsmTag("railway", "rail", "nuisances", weight=1.2),
        OsmTag("railway", "yard", "nuisances", weight=1.0),
        OsmTag("aeroway", "aerodrome", "nuisances", weight=1.5),
        OsmTag("landuse", "industrial", "nuisances", weight=1.0),
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
            cls.TRANSIT_TAGS +
            cls.NUISANCES_TAGS +
            cls.COMMERCE_TAGS +
            cls.ENVIRONMENT_TAGS
        )

    @classmethod
    def get_tags_by_category(cls, category: str) -> list[OsmTag]:
        """Get tags for a specific category."""
        mapping = {
            "education": cls.EDUCATION_TAGS,
            "transport": cls.TRANSPORT_TAGS,
            "transit": cls.TRANSIT_TAGS,
            "nuisances": cls.NUISANCES_TAGS,
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
