"""Tests pour les builders GeoJSON DuckDB."""

import json

from pyproj import Transformer

from app.infrastructure import data_availability
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

    def test_counts_transactions_inside_parcel(self, duckdb_conn_with_fixtures):
        """Une vente situee dans la parcelle est comptee.

        Regression : sans `always_xy`, DuckDB lisait EPSG:4326 en (lat, lon)
        et le compte valait 0 sur toutes les parcelles.
        """
        conn = duckdb_conn_with_fixtures
        conn.execute("""
            INSERT INTO france_foncier_test VALUES
            ('MUT003', -1.6778, 48.1173, 3200.0, '2024-03-01', 250000.0, 'Vente', FALSE)
        """)
        data = json.loads(build_parcelles_geojson(
            conn, min_x=-2.0, max_x=-1.0, min_y=48.0, max_y=49.0, dept_prefix="35",
        ))
        assert data["features"][0]["properties"]["transaction_count"] == 1

    def test_carries_map_mode_values(self, duckdb_conn_with_fixtures):
        """Prix moyen hors valeurs atypiques, categorie de densification, zone PLU."""
        data_availability.reset_cache()
        conn = duckdb_conn_with_fixtures
        conn.execute("ALTER TABLE france_foncier_test ADD COLUMN cadastre_parcelle_id VARCHAR")
        conn.execute("""
            INSERT INTO france_foncier_test VALUES
            ('MUT003', -1.6778, 48.1173, 3200.0, '2024-03-01', 250000.0, 'Vente', FALSE,
             '35238000AB0297')
        """)
        # MUT002 est atypique : il ne doit pas entrer dans la moyenne.
        conn.execute("UPDATE france_foncier_test SET cadastre_parcelle_id = '35238000AB0297'")
        conn.execute("CREATE TABLE densification_scores (id_parcelle VARCHAR, categorie VARCHAR)")
        conn.execute("INSERT INTO densification_scores VALUES ('35238000AB0297', 'FORT')")
        conn.execute("CREATE TABLE gpu_parcelles (id_parcelle VARCHAR, typezone VARCHAR)")
        conn.execute("INSERT INTO gpu_parcelles VALUES ('35238000AB0297', 'AUc')")

        data = json.loads(build_parcelles_geojson(
            conn, min_x=-2.0, max_x=-1.0, min_y=48.0, max_y=49.0, dept_prefix="35",
        ))
        props = data["features"][0]["properties"]
        assert props["prix_m2_moyen"] == 2850.0
        assert props["densification_categorie"] == "FORT"
        assert props["zone_plu"] == "AU"

    def test_missing_sources_leave_values_absent(self, duckdb_conn_with_fixtures):
        """Sans source, la propriete manque : le frontend hachure, il ne lit pas un zero."""
        data_availability.reset_cache()
        data = json.loads(build_parcelles_geojson(
            duckdb_conn_with_fixtures,
            min_x=-2.0, max_x=-1.0, min_y=48.0, max_y=49.0, dept_prefix="35",
        ))
        props = data["features"][0]["properties"]
        assert set(props) == {"id_parcelle", "transaction_count"}


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
