"""Tests de l'endpoint /filiation avec des données DFI réellement chargées.

`test_api_endpoints.py` vérifie le cas « table absente » (503 explicite).
Ici on charge une table `dfi_filiations` et on vérifie ce que l'API répond
quand la donnée existe — ce que rien ne couvrait, la table n'ayant jamais été
construite pour aucun département.
"""

import duckdb
import pytest
from fastapi.testclient import TestClient

from app.infrastructure import data_availability, duckdb_spatial

COMMUNE_3 = "256"          # code commune sur 3 chiffres, tel que stocké par le DFI
FILLE = "35256000AV0392"   # issue d'une division
MERE = "AV0107"
PETITE_FILLE = "35256000AV0500"  # arrière-petite-fille : chaîne de 3 générations
ORIGINELLE = "35256000AV9999"    # aucune ligne DFI


def _build_db(path) -> None:
    conn = duckdb.connect(str(path))
    conn.execute("INSTALL spatial; LOAD spatial;")
    conn.execute("""
        CREATE TABLE dfi_filiations (
            code_departement VARCHAR, code_commune VARCHAR, prefixe VARCHAR,
            id_dfi VARCHAR, nature_dfi VARCHAR, date_validation DATE,
            numero_lot VARCHAR, parcelle_mere VARCHAR, parcelle_fille VARCHAR
        )
    """)
    conn.execute(f"""
        INSERT INTO dfi_filiations VALUES
        -- AV0392 est issue de AV0107 (arpentage, 2008)
        ('035', '{COMMUNE_3}', '000', '0000001', '1', DATE '2008-02-25',
         '00001', '{MERE}', 'AV0392'),
        -- chaine a trois maillons : AV0500 <- AV0392 <- AV0107
        ('035', '{COMMUNE_3}', '000', '0000002', '7', DATE '2015-06-10',
         '00002', 'AV0392', 'AV0500')
    """)
    # `parcelles` est necessaire au controle de coherence geometrique.
    conn.execute("""
        CREATE TABLE parcelles (
            id_parcelle VARCHAR, code_commune VARCHAR, prefixe VARCHAR,
            section VARCHAR, numero VARCHAR, geometry GEOMETRY
        )
    """)
    conn.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
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


class TestFiliationAvecDonnees:
    def test_parcelle_issue_d_une_division(self, client):
        r = client.get(f"/api/v1/filiation/{FILLE}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ancestors"], "la parcelle a une mere connue"
        assert body["ancestors"][0]["id_parcelle"] == MERE
        assert body["ancestors"][0]["date_division"] == "2008-02-25"

    def test_depth_compte_les_generations_pas_la_racine(self, client):
        """`depth` doit valoir le nombre d'ancetres remontes.

        L'endpoint renvoyait `node.depth`, la profondeur du noeud racine —
        toujours 0. Le front affiche « {{ depth }} generation(s) » : il ne
        montrait donc jamais rien.
        """
        body = client.get(f"/api/v1/filiation/{FILLE}").json()
        assert body["depth"] == 1

    def test_depth_sur_une_chaine_de_deux_generations(self, client):
        body = client.get(f"/api/v1/filiation/{PETITE_FILLE}").json()
        assert body["depth"] == 2
        assert [a["id_parcelle"] for a in body["ancestors"]] == ["AV0107", "AV0392"]

    def test_parcelle_originelle_est_une_vraie_reponse(self, client):
        """Sans ligne DFI mais avec la table presente, « originelle » est exact."""
        r = client.get(f"/api/v1/filiation/{ORIGINELLE}")
        assert r.status_code == 200
        body = r.json()
        assert body["depth"] == 0
        assert body["ancestors"] == []
        assert "originelle" in body["filiation_summary"].lower()

    def test_nature_operation_remontee(self, client):
        body = client.get(f"/api/v1/filiation/{FILLE}").json()
        assert body["ancestors"][0]["nature_operation"] == "1"

    def test_coherence_geo_non_verifiable_si_mere_disparue(self, client):
        """Une mere divisee n'existe plus au cadastre : rien a comparer.

        NON_VERIFIABLE est ici la reponse correcte, pas un echec.
        """
        body = client.get(f"/api/v1/filiation/{FILLE}").json()
        assert body["ancestors"][0]["coherence_geo"] == "NON_VERIFIABLE"

    def test_arbre_structure_coherent_avec_la_chaine(self, client):
        body = client.get(f"/api/v1/filiation/{PETITE_FILLE}").json()
        tree = body["tree"]
        assert tree["id_parcelle"] == "AV0500"
        assert tree["parent"]["id_parcelle"] == "AV0392"
        assert tree["parent"]["parent"]["id_parcelle"] == "AV0107"
        assert tree["parent"]["parent"]["parent"] is None
