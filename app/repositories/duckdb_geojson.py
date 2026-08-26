"""GeoJSON builders for DuckDB parcel and transaction data."""

import json
import logging
from typing import Any

from pyproj import Transformer

logger = logging.getLogger(__name__)


def build_transactions_geojson(
    conn: Any,
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    limit: int = 1000,
) -> str:
    """Build GeoJSON FeatureCollection of transaction points."""
    query = """
        SELECT id_mutation, longitude, latitude, prix_m2,
               date_mutation, valeur_fonciere, nature_mutation,
               COALESCE(is_outlier, FALSE) AS is_outlier
        FROM france_foncier_test
        WHERE longitude BETWEEN ? AND ? AND latitude BETWEEN ? AND ?
          AND longitude IS NOT NULL AND latitude IS NOT NULL
        LIMIT ?
    """
    try:
        results = conn.execute(query, [min_x, max_x, min_y, max_y, limit]).fetchall()
        logger.debug("get_transactions_geojson found %d transactions", len(results))
    except Exception as e:
        logger.warning("get_transactions_geojson failed: %s", e)
        return '{"type": "FeatureCollection", "features": []}'

    features = []
    for r in results:
        props = [f'"id": "{r[0]}"']
        if r[3]:
            props.append(f'"prix_m2": {float(r[3])}')
        if r[4]:
            props.append(f'"date": "{r[4]}"')
        if r[5]:
            props.append(f'"valeur_fonciere": {float(r[5])}')
        if r[6]:
            props.append(f'"nature": "{r[6]}"')
        props.append(f'"is_outlier": {str(bool(r[7])).lower()}')
        features.append(
            f'{{"type": "Feature", "properties": {{{", ".join(props)}}}, '
            f'"geometry": {{"type": "Point", "coordinates": [{float(r[1])}, {float(r[2])}]}}}}'
        )
    return '{"type": "FeatureCollection", "features": [' + ",".join(features) + ']}'


def build_parcelles_geojson(
    conn: Any,
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    limit: int = 500,
    filter: str | None = None,
) -> str:
    """Build GeoJSON FeatureCollection of parcel polygons with transaction counts.
    filter: 'zan' (categorie FORT) or 'recent' (vente < 2 ans).
    """
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:2154", always_xy=True)
    min_x_l93, min_y_l93 = transformer.transform(min_x, min_y)
    max_x_l93, max_y_l93 = transformer.transform(max_x, max_y)

    logger.debug("Parcelles bbox WGS84 (%.2f,%.2f)-(%.2f,%.2f) -> L93 (%.2f,%.2f)-(%.2f,%.2f)",
                 min_x, min_y, max_x, max_y, min_x_l93, min_y_l93, max_x_l93, max_y_l93)

    filter_clause = ""
    parcelle_id_expr = "CONCAT(COALESCE(p.code_commune,''), COALESCE(p.prefixe,'000'), COALESCE(p.section,''), LPAD(COALESCE(p.numero,''),4,'0'))"
    if filter == "zan":
        filter_clause = f"""
          AND EXISTS (
            SELECT 1 FROM densification_scores d
            WHERE d.id_parcelle = {parcelle_id_expr} AND d.categorie = 'FORT'
          )"""
    elif filter == "recent":
        filter_clause = f"""
          AND EXISTS (
            SELECT 1 FROM france_foncier_test f
            WHERE f.cadastre_parcelle_id = {parcelle_id_expr}
              AND TRY_CAST(f.date_mutation AS DATE) >= CURRENT_DATE - INTERVAL 2 YEARS
              AND f.longitude BETWEEN ? AND ? AND f.latitude BETWEEN ? AND ?
          )"""

    parcelles_query = f"""
        SELECT CONCAT(COALESCE(p.code_commune,''), COALESCE(p.prefixe,'000'),
               COALESCE(p.section,''), LPAD(COALESCE(p.numero,''),4,'0')) as full_id_parcelle,
               ST_AsText(p.geometry), ST_AsGeoJSON(p.geometry), ST_Area(p.geometry)
        FROM parcelles p
        WHERE p.code_commune LIKE '35%'
          AND ST_Intersects(p.geometry, ST_MakeEnvelope(?, ?, ?, ?))
          AND ST_Area(p.geometry) < 10000 AND ST_Area(p.geometry) > 10
        {filter_clause}
        LIMIT ?
    """
    try:
        parcelles_params: list = [min_x_l93, min_y_l93, max_x_l93, max_y_l93]
        if filter == "recent":
            parcelles_params.extend([min_x, max_x, min_y, max_y])
        parcelles_params.append(limit)
        parcelles_results = conn.execute(parcelles_query, parcelles_params).fetchall()
    except Exception as e:
        logger.exception("get_parcelles_geojson failed: %s", e)
        return '{"type": "FeatureCollection", "features": []}'

    count_query = """
        WITH tx_points AS (
            SELECT id_mutation,
                   ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:2154') as geom_l93
            FROM france_foncier_test
            WHERE longitude BETWEEN ? AND ? AND latitude BETWEEN ? AND ?
              AND longitude IS NOT NULL AND latitude IS NOT NULL
        ),
        parcel_bounds AS (
            SELECT CONCAT(COALESCE(p.code_commune,''), COALESCE(p.prefixe,'000'),
                   COALESCE(p.section,''), LPAD(COALESCE(p.numero,''),4,'0')) as id_parcelle,
                   p.geometry
            FROM parcelles p
            WHERE p.code_commune LIKE '35%'
              AND ST_Intersects(p.geometry, ST_MakeEnvelope(?, ?, ?, ?))
              AND ST_Area(p.geometry) < 10000 AND ST_Area(p.geometry) > 10
            LIMIT ?
        )
        SELECT pb.id_parcelle, COUNT(tx.id_mutation)
        FROM parcel_bounds pb
        LEFT JOIN tx_points tx ON ST_Contains(pb.geometry, tx.geom_l93)
        GROUP BY pb.id_parcelle
    """
    try:
        tx_counts = dict(conn.execute(count_query, [
            min_x, max_x, min_y, max_y,
            min_x_l93, min_y_l93, max_x_l93, max_y_l93,
            limit
        ]).fetchall())
    except Exception as e:
        logger.warning("SQL spatial join failed: %s", e)
        tx_counts = {}

    transformer_out = Transformer.from_crs("EPSG:2154", "EPSG:4326", always_xy=True)
    features = []
    seen = set()
    for r in parcelles_results:
        parcel_id, geom_json_l93 = r[0], r[2]
        if parcel_id in seen or not geom_json_l93:
            continue
        seen.add(parcel_id)
        geom_l93 = json.loads(geom_json_l93)
        geom_wgs84 = _transform_geom_to_wgs84(geom_l93, transformer_out)
        tx_count = tx_counts.get(parcel_id, 0)
        props = f'"id_parcelle": "{parcel_id}", "transaction_count": {tx_count}'
        features.append(f'{{"type": "Feature", "properties": {{{props}}}, "geometry": {json.dumps(geom_wgs84)}}}')
    return '{"type": "FeatureCollection", "features": [' + ",".join(features) + ']}'


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
