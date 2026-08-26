"""Tests pour les builders GeoJSON DuckDB."""

import json

from pyproj import Transformer

from app.repositories.duckdb_geojson import (
    _transform_geom_to_wgs84,
    build_parcelles_geojson,
    build_transactions_geojson,
)


class TestBuildTransactionsGeojson:
    """Tests de build_transactions_geojson."""

    def test_returns_valid_geojson(self, duckdb_conn_with_fixtures):
        geojson = build_transactions_geojson(
            duckdb_conn_with_fixtures,
            min_x=-2.0, max_x=-1.0,
            min_y=48.0, max_y=49.0,
            limit=10,
        )
        data = json.loads(geojson)
        assert data["type"] == "FeatureCollection"
        assert "features" in data
        assert len(data["features"]) == 2

    def test_feature_has_point_geometry(self, duckdb_conn_with_fixtures):
        geojson = build_transactions_geojson(
            duckdb_conn_with_fixtures,
            min_x=-2.0, max_x=-1.0,
            min_y=48.0, max_y=49.0,
        )
        data = json.loads(geojson)
        feat = data["features"][0]
        assert feat["geometry"]["type"] == "Point"
        assert len(feat["geometry"]["coordinates"]) == 2

    def test_feature_has_properties(self, duckdb_conn_with_fixtures):
        geojson = build_transactions_geojson(
            duckdb_conn_with_fixtures,
            min_x=-2.0, max_x=-1.0,
            min_y=48.0, max_y=49.0,
        )
        data = json.loads(geojson)
        feat = data["features"][0]
        assert "id" in feat["properties"]
        assert "prix_m2" in feat["properties"]

    def test_empty_when_no_data(self, duckdb_conn_inmemory):
        geojson = build_transactions_geojson(
            duckdb_conn_inmemory,
            min_x=-2.0, max_x=-1.0,
            min_y=48.0, max_y=49.0,
        )
        data = json.loads(geojson)
        assert data["type"] == "FeatureCollection"
        assert data["features"] == []


class TestBuildParcellesGeojson:
    """Tests de build_parcelles_geojson.

    Le filtre departemental n'est plus code en dur : il se passe via
    `dept_prefix`. Les fixtures utilisent des parcelles 35238 (Rennes).
    """

    def test_returns_valid_geojson(self, duckdb_conn_with_fixtures):
        geojson = build_parcelles_geojson(
            duckdb_conn_with_fixtures,
            min_x=-2.0, max_x=-1.0,
            min_y=48.0, max_y=49.0,
            limit=100,
            dept_prefix="35",
        )
        data = json.loads(geojson)
        assert data["type"] == "FeatureCollection"
        assert "features" in data

    def test_respects_limit(self, duckdb_conn_with_fixtures):
        geojson = build_parcelles_geojson(
            duckdb_conn_with_fixtures,
            min_x=-2.0, max_x=-1.0,
            min_y=48.0, max_y=49.0,
            limit=1,
            dept_prefix="35",
        )
        data = json.loads(geojson)
        assert len(data["features"]) <= 1


class TestTransformGeomToWgs84:
    """Tests de _transform_geom_to_wgs84."""

    def test_polygon_transform(self):
        transformer = Transformer.from_crs("EPSG:2154", "EPSG:4326", always_xy=True)
        geom = {
            "type": "Polygon",
            "coordinates": [[
                [352100, 6789900], [352200, 6789900], [352200, 6790000],
                [352100, 6790000], [352100, 6789900],
            ]],
        }
        out = _transform_geom_to_wgs84(geom, transformer)
        assert out["type"] == "Polygon"
        assert len(out["coordinates"]) == 1
        ring = out["coordinates"][0]
        assert len(ring) == 5
        lon, lat = ring[0]
        assert -2 < lon < 0
        assert 48 < lat < 50

    def test_multipolygon_transform(self):
        transformer = Transformer.from_crs("EPSG:2154", "EPSG:4326", always_xy=True)
        geom = {
            "type": "MultiPolygon",
            "coordinates": [
                [[[352100, 6789900], [352200, 6789900], [352200, 6790000], [352100, 6789900]]],
            ],
        }
        out = _transform_geom_to_wgs84(geom, transformer)
        assert out["type"] == "MultiPolygon"
        assert len(out["coordinates"]) == 1
