"""Tests SQL de `get_parents` / `get_children`, contre une vraie base.

`test_filiation.py` couvre l'arbre, mais via `MockFiliationRepository`, qui
remplace justement ces deux methodes : toute la couche SQL de la filiation
n'etait exercee nulle part. Le trou s'est vu en inversant volontairement les
colonnes interrogees — les 28 tests existants restaient verts.

Ces tests portent donc sur ce que le mock ne peut pas voir : quelle colonne
est interrogee dans quel sens, et ce qui se passe sans table DFI.
"""

from datetime import date

import duckdb
import pytest

from app.domain.filiation_models import DFINature
from app.infrastructure.data_availability import DataUnavailableError, reset_cache
from app.infrastructure.duckdb_pool import close_shared_connection
from app.repositories.filiation_repository import DuckDBFiliationRepository

COMMUNE = "001"

# Genealogie de test, sur trois generations :
#   AB0005 --> AC0001 --> AC0010
#                     \-> AC0011
_LIENS = [
    # (id_dfi, mere,     fille,    date)
    ("D000001", "AB0005", "AC0001", "2019-05-10"),
    ("D000002", "AC0001", "AC0010", "2021-03-01"),
    ("D000003", "AC0001", "AC0011", "2022-07-15"),
]


@pytest.fixture
def base_dfi(tmp_path):
    """Base portant `dfi_filiations` seule."""
    chemin = tmp_path / "filiation.duckdb"
    conn = duckdb.connect(str(chemin))
    conn.execute("""
        CREATE TABLE dfi_filiations (
            id_dfi VARCHAR, code_departement VARCHAR, code_commune VARCHAR,
            prefixe VARCHAR, nature_dfi VARCHAR, date_validation DATE,
            numero_lot VARCHAR, parcelle_mere VARCHAR, parcelle_fille VARCHAR
        )
    """)
    for id_dfi, mere, fille, jour in _LIENS:
        conn.execute(
            "INSERT INTO dfi_filiations VALUES (?, '035', ?, '000', ?, ?, 'L0001', ?, ?)",
            [id_dfi, COMMUNE, DFINature.ARPENTAGE.value, jour, mere, fille],
        )
    conn.close()
    reset_cache()
    yield chemin
    close_shared_connection(chemin)
    reset_cache()


@pytest.fixture
def base_sans_dfi(tmp_path):
    """Base ou l'ETL DFI n'a jamais tourne."""
    chemin = tmp_path / "vide.duckdb"
    conn = duckdb.connect(str(chemin))
    conn.execute("CREATE TABLE autre (x INTEGER)")
    conn.close()
    reset_cache()
    yield chemin
    close_shared_connection(chemin)
    reset_cache()


@pytest.fixture
def depot(base_dfi):
    return DuckDBFiliationRepository(base_dfi)


def test_get_parents_remonte_a_la_mere(depot):
    parents = depot.get_parents(COMMUNE, "AC", "10")

    assert [p.parcelle_mere for p in parents] == ["AC0001"]
    assert parents[0].parcelle_fille == "AC0010"
    assert parents[0].id_dfi == "D000002"
    assert parents[0].date_validation == date(2021, 3, 1)


def test_get_children_descend_aux_filles(depot):
    enfants = depot.get_children(COMMUNE, "AC", "1")

    # Tri par date decroissante : AC0011 (2022) avant AC0010 (2021).
    assert [e.parcelle_fille for e in enfants] == ["AC0011", "AC0010"]
    assert {e.parcelle_mere for e in enfants} == {"AC0001"}


def test_les_deux_sens_ne_sont_pas_symetriques(depot):
    """Le test qui attrape une inversion des colonnes interrogees.

    AC0010 est une fille sans descendance : elle a un parent et aucun enfant.
    Interroger `parcelle_fille` au lieu de `parcelle_mere` dans `get_children`
    lui inventerait un enfant, et c'est precisement l'erreur qu'une
    factorisation des deux methodes peut introduire sans bruit.
    """
    assert depot.get_parents(COMMUNE, "AC", "10") != []
    assert depot.get_children(COMMUNE, "AC", "10") == []

    # Et symetriquement sur la racine connue de la chaine.
    assert depot.get_children(COMMUNE, "AB", "5") != []
    assert depot.get_parents(COMMUNE, "AB", "5") == []


def test_numero_complete_a_quatre_chiffres(depot):
    """`numero` est zero-padde : '1', '01' et '0001' designent AC0001."""
    attendu = [e.parcelle_fille for e in depot.get_children(COMMUNE, "AC", "1")]

    assert [e.parcelle_fille for e in depot.get_children(COMMUNE, "AC", "01")] == attendu
    assert [e.parcelle_fille for e in depot.get_children(COMMUNE, "AC", "0001")] == attendu


def test_parcelle_inconnue_donne_liste_vide(depot):
    assert depot.get_parents(COMMUNE, "ZZ", "9999") == []
    assert depot.get_children(COMMUNE, "ZZ", "9999") == []


def test_autre_commune_ignoree(depot):
    assert depot.get_parents("999", "AC", "10") == []


def test_sans_table_dfi_le_depot_refuse_de_repondre(base_sans_dfi):
    """Sans la garde, l'API concluait « parcelle originelle » pour tout le departement."""
    depot = DuckDBFiliationRepository(base_sans_dfi)

    with pytest.raises(DataUnavailableError):
        depot.get_parents(COMMUNE, "AC", "10")
    with pytest.raises(DataUnavailableError):
        depot.get_children(COMMUNE, "AC", "10")
