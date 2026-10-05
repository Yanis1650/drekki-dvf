"""Reprojection des geometries pour la sortie GeoJSON.

Les geometries sont stockees en Lambert-93 (EPSG:2154) et servies en
WGS84, seul systeme que la norme GeoJSON admette.
"""

from pyproj import Transformer


def _transform_geom_to_wgs84(geom: dict, transformer: Transformer) -> dict:
    """Transform Lambert-93 geometry to WGS84."""
    if geom["type"] == "Polygon":
        transformed = [
            [list(transformer.transform(x, y)) for x, y in ring]
            for ring in geom["coordinates"]
        ]
        return {"type": "Polygon", "coordinates": transformed}
    if geom["type"] == "MultiPolygon":
        transformed = [
            [[list(transformer.transform(x, y)) for x, y in ring] for ring in poly]
            for poly in geom["coordinates"]
        ]
        return {"type": "MultiPolygon", "coordinates": transformed}
    return geom
