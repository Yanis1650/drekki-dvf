"""Tests des endpoints HTTP.

Le projet n'en avait aucun : c'est ce qui a laissé passer une fiche parcelle en
erreur 500 (colonne inexistante), une filiation qui affirmait « parcelle
originelle » faute de données, et une route de crédits que le front appelait
sous un autre nom. Ces tests montent l'application sur une base DuckDB
temporaire au contenu maîtrisé et vérifient le contrat réellement servi.
"""

import duckdb
import pytest
from fastapi.testclient import TestClient

from app.infrastructure import data_availability, duckdb_spatial

COMMUNE = "35238"
PARCELLE = "35238000AB0297"
PARCELLE_SANS_DONNEES = "35999000ZZ9999"


def _build_db(path) -> None:
    """Construit une base minimale mais fidèle au schéma de production."""
    conn = duckdb.connect(str(path))
    conn.execute("INSTALL spatial; LOAD spatial;")
    conn.execute("""
        CREATE TABLE france_foncier_test (
            id_mutation VARCHAR,
            date_mutation VARCHAR,
            nature_mutation VARCHAR,
            valeur_fonciere DOUBLE,
            code_commune VARCHAR,
            dvf_parcelles VARCHAR,
            surface_habitable_totale DOUBLE,
            nombre_locaux INTEGER,
            prix_m2 DOUBLE,
            longitude DOUBLE,
            latitude DOUBLE,
            cadastre_parcelle_id VARCHAR,
            dpe_energie VARCHAR,
            annee_construction INTEGER,
            hauteur_moyenne DOUBLE,
            nb_niveau INTEGER,
            type_usage VARCHAR,
            nb_log INTEGER,
            is_outlier BOOLEAN
        )
    """)
    conn.execute(f"""
        INSERT INTO france_foncier_test VALUES
        ('MUT001', '2024-01-15', 'Vente', 250000.0, '{COMMUNE}', '{PARCELLE}',
         100.0, 1, 2500.0, -1.6778, 48.1173, '{PARCELLE}',
         'C', 1985, 6.0, 2, 'residentiel', 1, FALSE),
        ('MUT002', '2023-06-20', 'Vente', 180000.0, '{COMMUNE}', '{PARCELLE}',
         60.0, 1, 3000.0, -1.6790, 48.1180, '{PARCELLE}',
         'D', 1970, 6.0, 2, 'residentiel', 1, FALSE)
    """)
    conn.execute("""
        CREATE TABLE densification_scores (
            id_parcelle VARCHAR, code_commune VARCHAR,
            surface_parcelle_m2 DOUBLE, surface_plancher_m2 DOUBLE,
            emprise_sol_m2 DOUBLE, ces_actuel DOUBLE, ces_potentiel DOUBLE,
            potentiel_densification DOUBLE, surface_constructible_restante DOUBLE,
            source_ces VARCHAR, type_usage VARCHAR, nb_niveau INTEGER,
            categorie VARCHAR, plu_datappro DATE, libelle_zone VARCHAR,
            zone_non_mutable BOOLEAN
        )
    """)
    conn.execute(f"""
        INSERT INTO densification_scores VALUES
        ('{PARCELLE}', '{COMMUNE}', 1000.0, 200.0, 100.0, 0.20, 0.40,
         0.20, 200.0, 'plu_gpu', 'residentiel', 2, 'FORT', DATE '2020-01-01',
         'UA', FALSE)
    """)
    # La colonne physique s'appelle score_zan : le test verrouille l'alias
    # score_densification exposé par l'API.
    conn.execute("""
        CREATE TABLE confidence_scores (
            id_parcelle VARCHAR, score_bdnb DOUBLE, score_dvf_fiabilite DOUBLE,
            score_dvf_precision DOUBLE, score_zan DOUBLE, score_fraicheur DOUBLE,
            score_dvf DOUBLE, confidence_global DOUBLE, confidence_label VARCHAR
        )
    """)
    conn.execute(f"""
        INSERT INTO confidence_scores VALUES
        ('{PARCELLE}', 0.9, 0.8, 0.8, 0.7, 0.6, 0.8, 0.78, 'Elevee')
    """)
    # Table lue par la recherche par rayon (get_mutations_in_radius).
    conn.execute("""
        CREATE TABLE mutations_aggregated (
            id_mutation VARCHAR, date_mutation VARCHAR, nature_mutation VARCHAR,
            valeur_fonciere DOUBLE, code_commune VARCHAR, parcelles VARCHAR[],
            surface_habitable_totale DOUBLE, nombre_locaux INTEGER,
            prix_m2 DOUBLE, longitude DOUBLE, latitude DOUBLE, type_local VARCHAR
        )
    """)
    conn.execute(f"""
        INSERT INTO mutations_aggregated VALUES
        ('MUT001', '2024-01-15', 'Vente', 250000.0, '{COMMUNE}', ['{PARCELLE}'],
         100.0, 1, 2500.0, -1.6778, 48.1173, 'Maison'),
        ('MUT002', '2023-06-20', 'Vente', 180000.0, '{COMMUNE}', ['{PARCELLE}'],
         60.0, 1, 3000.0, -1.6790, 48.1180, 'Appartement')
    """)
    conn.execute("""
        CREATE TABLE parcelles (
            id_parcelle VARCHAR, code_commune VARCHAR, prefixe VARCHAR,
            section VARCHAR, numero VARCHAR, surface_m2 DOUBLE, geometry GEOMETRY
        )
    """)
    conn.execute(f"""
        INSERT INTO parcelles VALUES
        ('{PARCELLE}', '{COMMUNE}', '000', 'AB', '0297', 1000.0,
         ST_GeomFromText('POLYGON((352100 6789900, 352200 6789900, 352200 6790000, 352100 6790000, 352100 6789900))'))
    """)
    conn.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Application montée sur une base temporaire.

    `get_settings` est mis en cache par `lru_cache` : on le vide de part et
    d'autre pour que le chemin DuckDB du test ne fuite pas vers les suivants.
    """
    from conftest import SPATIAL_AVAILABLE

    if not SPATIAL_AVAILABLE:
        pytest.skip("extension DuckDB spatial indisponible dans cet environnement")

    db_path = tmp_path / "dept35.duckdb"
    _build_db(db_path)

    monkeypatch.setenv("DUCKDB_PATH", str(db_path))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MULTI_DEPT", "false")

    from app.api.deps import get_settings

    get_settings.cache_clear()
    data_availability.reset_cache()
    duckdb_spatial.reset_cache()

    from app.main import app

    with TestClient(app) as c:
        yield c

    get_settings.cache_clear()
    data_availability.reset_cache()
    duckdb_spatial.reset_cache()


class TestHealth:
    def test_racine(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_v1(self, client):
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        assert r.json()["database"] == "duckdb"


class TestFicheParcelle:
    """Non-régression : la fiche renvoyait 500 (colonne score_densification)."""

    def test_fiche_repond_200(self, client):
        r = client.get(f"/api/v1/land/parcelles/{PARCELLE}/fiche")
        assert r.status_code == 200, r.text

    def test_fiche_expose_score_densification(self, client):
        """L'API expose `score_densification`, alimenté par la colonne score_zan."""
        body = client.get(f"/api/v1/land/parcelles/{PARCELLE}/fiche").json()
        assert body["score_densification"] == pytest.approx(0.7)

    def test_fiche_contient_densification_et_confiance(self, client):
        body = client.get(f"/api/v1/land/parcelles/{PARCELLE}/fiche").json()
        assert body["id_parcelle"] == PARCELLE
        assert body["nb_transactions"] == 2
        assert body["categorie_densification"] == "FORT"
        assert body["confidence_label"] == "Elevee"
        assert body["source_ces"] == "plu_gpu"

    def test_fiche_expose_le_libelle_de_zone_plu(self, client):
        """Le front lie `fiche.libelle_zone` : l'API doit le fournir."""
        body = client.get(f"/api/v1/land/parcelles/{PARCELLE}/fiche").json()
        assert body["libelle_zone"] == "UA"
        assert body["plu_datappro"] == "2020-01-01"

    def test_parcelle_inconnue_renvoie_404(self, client):
        r = client.get(f"/api/v1/land/parcelles/{PARCELLE_SANS_DONNEES}/fiche")
        assert r.status_code == 404


class TestFiliationDonneesAbsentes:
    """Non-régression : sans table DFI, l'API affirmait « parcelle originelle »."""

    def test_renvoie_503_et_non_une_reponse_inventee(self, client):
        r = client.get(f"/api/v1/filiation/{PARCELLE}")
        assert r.status_code == 503, r.text
        body = r.json()
        assert body["error"] == "data_unavailable"
        assert "dfi_filiations" in body["detail"]

    def test_ne_pretend_pas_que_la_parcelle_est_originelle(self, client):
        r = client.get(f"/api/v1/filiation/{PARCELLE}")
        assert "originelle" not in r.text.lower()


class TestRechercheEnrichie:
    """Sans POI chargés, les scores doivent être omis, pas inventés."""

    def test_signale_enrichissement_indisponible(self, client):
        r = client.get(
            "/api/v1/land/search/enriched",
            params={"lat": 48.1173, "lon": -1.6778, "radius": 2000, "limit": 10},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["enrichment_available"] is False
        assert body["location_enrichment"] is None

    def test_aucun_score_neutre_invente(self, client):
        body = client.get(
            "/api/v1/land/search/enriched",
            params={"lat": 48.1173, "lon": -1.6778, "radius": 2000, "limit": 10},
        ).json()
        assert body["mutations"], "les mutations doivent bien remonter"
        assert all(m["enrichment"] is None for m in body["mutations"])

    def test_les_mutations_restent_servies(self, client):
        body = client.get(
            "/api/v1/land/search/enriched",
            params={"lat": 48.1173, "lon": -1.6778, "radius": 2000, "limit": 10},
        ).json()
        assert body["mutations_count"] == 2
        assert body["avg_price_m2"] is not None


class TestGeojson:
    def test_bbox_manquante_renvoie_422(self, client):
        assert client.get("/api/v1/land/geojson").status_code == 422

    def test_bbox_trop_large_renvoie_400(self, client):
        r = client.get("/api/v1/land/geojson", params={"bbox": "-5,45,5,52"})
        assert r.status_code == 400

    def test_transactions_geojson(self, client):
        r = client.get("/api/v1/land/geojson", params={"bbox": "-1.7,48.1,-1.6,48.2"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["type"] == "FeatureCollection"
        assert len(body["features"]) == 2
        assert body["features"][0]["geometry"]["type"] == "Point"

    def test_parcelles_geojson(self, client):
        r = client.get("/api/v1/land/parcelles", params={"bbox": "-1.7,48.1,-1.6,48.2"})
        assert r.status_code == 200, r.text
        assert r.json()["type"] == "FeatureCollection"

    def test_filtre_invalide_renvoie_400(self, client):
        r = client.get(
            "/api/v1/land/parcelles",
            params={"bbox": "-1.7,48.1,-1.6,48.2", "filter": "nimportequoi"},
        )
        assert r.status_code == 400


class TestAnalytics:
    def test_tendances_marche(self, client):
        r = client.get("/api/v1/analytics/trends", params={"code_commune": COMMUNE})
        assert r.status_code == 200, r.text

    def test_historique_parcelle(self, client):
        r = client.get(f"/api/v1/analytics/parcel/{PARCELLE}/history")
        assert r.status_code == 200, r.text


class TestSurfaceDApi:
    """L'application est libre : aucune route d'authentification ni de paiement."""

    def test_aucune_route_utilisateur_ou_credit(self, client):
        paths = client.get("/openapi.json").json()["paths"]
        interdits = [p for p in paths if "user" in p or "credit" in p]
        assert interdits == []

    def test_api_en_lecture_seule(self, client):
        paths = client.get("/openapi.json").json()["paths"]
        methodes = {m.upper() for ops in paths.values() for m in ops}
        assert methodes <= {"GET", "HEAD"}, f"méthodes inattendues : {methodes}"
