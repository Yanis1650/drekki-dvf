"""Tests de `DvfRepository` — le filet manquant avant refonte.

Ce depot est le seul repository de `app/repositories/` qu'aucun test ne
touchait, alors qu'il porte 390 lignes et cinq methodes du contrat
`ITransactionRepository`. Le decouper sans filet, c'etait accepter de casser
sans le voir.

Chaque test ouvre un vrai fichier DuckDB : la connexion partagee est ouverte en
lecture seule, donc les tables sont creees puis la connexion d'ecriture fermee
avant que le repository n'ouvre la sienne.
"""

import json
from datetime import date
from decimal import Decimal

import duckdb
import pytest
from conftest import requires_spatial

from app.domain.models import NatureMutation, TypeLocal
from app.infrastructure.duckdb_pool import close_shared_connection
from app.repositories.dvf_repository import DvfRepository

COMMUNE = "35238"  # Rennes
AUTRE_COMMUNE = "35047"


def _creer_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("""
        CREATE TABLE transactions (
            id_mutation VARCHAR, date_mutation DATE, nature_mutation VARCHAR,
            valeur_fonciere DOUBLE, code_commune VARCHAR, id_parcelle VARCHAR,
            type_local VARCHAR, surface_reelle_bati DOUBLE, nombre_pieces INTEGER
        )
    """)
    conn.execute(f"""
        INSERT INTO transactions VALUES
        ('MUT001', '2022-03-10', 'Vente', 150000, '{COMMUNE}', '35238000AB0297',
         'Maison', 80, 4),
        ('MUT002', '2023-06-20', 'Vente', 200000, '{COMMUNE}', '35238000AB0298',
         'Appartement', 50, 2),
        ('MUT003', '2024-01-15', 'Adjudication', 90000, '{COMMUNE}', '35238000AB0299',
         NULL, NULL, NULL),
        ('MUT004', '2023-09-01', 'Vente', 300000, '{AUTRE_COMMUNE}', '35047000AB0001',
         'Maison', 120, 5)
    """)
    conn.execute("""
        CREATE TABLE mutations_aggregated (
            id_mutation VARCHAR, date_mutation DATE, nature_mutation VARCHAR,
            valeur_fonciere DOUBLE, code_commune VARCHAR, parcelles VARCHAR[],
            surface_habitable_totale DOUBLE, nombre_locaux INTEGER,
            prix_m2 DOUBLE, longitude DOUBLE, latitude DOUBLE
        )
    """)
    # Rennes centre ~ (-1.6778, 48.1173). MUT012 est a ~8 km au nord.
    conn.execute(f"""
        INSERT INTO mutations_aggregated VALUES
        ('MUT010', '2022-03-10', 'Vente', 150000, '{COMMUNE}', ['35238000AB0297'],
         80, 1, 1875, -1.6778, 48.1173),
        ('MUT011', '2023-06-20', 'Adjudication', 200000, '{COMMUNE}', ['35238000AB0298'],
         50, 2, 4000, -1.6800, 48.1200),
        ('MUT012', '2024-01-15', 'Vente', 90000, '{COMMUNE}', ['35238000AB0299'],
         30, 1, 3000, -1.6778, 48.1900),
        ('MUT013', '2024-05-01', 'Vente', 120000, '{COMMUNE}', ['35238000AB0300'],
         60, 1, 2000, -1.6820, 48.1210)
    """)


def _creer_france_foncier_test(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("""
        CREATE TABLE france_foncier_test (
            id_mutation VARCHAR, code_commune VARCHAR, date_mutation DATE,
            longitude DOUBLE, latitude DOUBLE, prix_m2 DOUBLE,
            classe_consommation_energie VARCHAR, annee_construction INTEGER,
            valeur_fonciere DOUBLE, surface_reelle DOUBLE, is_outlier BOOLEAN
        )
    """)
    conn.execute(f"""
        INSERT INTO france_foncier_test VALUES
        ('MUT010', '{COMMUNE}', '2022-03-10', -1.6778, 48.1173, 2000, 'C', 1970,
         150000, 75, FALSE),
        ('MUT011', '{COMMUNE}', '2023-06-20', -1.6800, 48.1200, 4000, 'D', 2001,
         200000, 50, FALSE),
        ('MUT099', '{COMMUNE}', '2023-07-01', -1.6790, 48.1180, 99000, NULL, NULL,
         900000, 9, TRUE)
    """)


@pytest.fixture
def base_dvf(tmp_path):
    """Base complete : transactions, mutations agregees et table enrichie."""
    chemin = tmp_path / "dvf.duckdb"
    conn = duckdb.connect(str(chemin))
    _creer_tables(conn)
    _creer_france_foncier_test(conn)
    conn.close()
    yield chemin
    close_shared_connection(chemin)


@pytest.fixture
def base_sans_enrichie(tmp_path):
    """Base non encore buildee : `france_foncier_test` absente."""
    chemin = tmp_path / "dvf_brut.duckdb"
    conn = duckdb.connect(str(chemin))
    _creer_tables(conn)
    conn.close()
    yield chemin
    close_shared_connection(chemin)


@pytest.fixture
def depot(base_dvf):
    return DvfRepository(base_dvf)


# --- get_transactions_by_commune ------------------------------------------


async def test_transactions_par_commune_mappe_le_domaine(depot):
    transactions = await depot.get_transactions_by_commune(COMMUNE)

    assert [t.id_mutation for t in transactions] == ["MUT001", "MUT002", "MUT003"]
    premiere = transactions[0]
    assert premiere.valeur_fonciere == Decimal("150000")
    assert premiere.nature_mutation is NatureMutation.VENTE
    assert premiere.type_local is TypeLocal.MAISON
    assert premiere.surface_reelle_bati == Decimal("80")
    assert premiere.nombre_pieces == 4


async def test_transactions_colonnes_nulles_donnent_none(depot):
    transactions = await depot.get_transactions_by_commune(COMMUNE)
    sans_local = next(t for t in transactions if t.id_mutation == "MUT003")

    assert sans_local.type_local is None
    assert sans_local.surface_reelle_bati is None
    assert sans_local.nombre_pieces is None
    assert sans_local.nature_mutation is NatureMutation.ADJUDICATION


async def test_transactions_ignore_les_autres_communes(depot):
    transactions = await depot.get_transactions_by_commune(COMMUNE)
    assert all(t.code_commune == COMMUNE for t in transactions)


async def test_transactions_commune_inconnue_donne_liste_vide(depot):
    assert await depot.get_transactions_by_commune("99999") == []


async def test_transactions_filtre_date_from(depot):
    transactions = await depot.get_transactions_by_commune(
        COMMUNE, date_from=date(2023, 1, 1)
    )
    assert [t.id_mutation for t in transactions] == ["MUT002", "MUT003"]


async def test_transactions_filtre_date_to(depot):
    transactions = await depot.get_transactions_by_commune(
        COMMUNE, date_to=date(2023, 1, 1)
    )
    assert [t.id_mutation for t in transactions] == ["MUT001"]


async def test_transactions_filtre_intervalle_complet(depot):
    transactions = await depot.get_transactions_by_commune(
        COMMUNE, date_from=date(2023, 1, 1), date_to=date(2023, 12, 31)
    )
    assert [t.id_mutation for t in transactions] == ["MUT002"]


# --- get_mutations_by_commune ---------------------------------------------


async def test_mutations_par_commune_mappe_le_domaine(depot):
    mutations = await depot.get_mutations_by_commune(COMMUNE)

    assert [m.id_mutation for m in mutations] == ["MUT010", "MUT011", "MUT012", "MUT013"]
    premiere = mutations[0]
    assert premiere.date_mutation == date(2022, 3, 10)
    assert premiere.valeur_fonciere == Decimal("150000")
    assert premiere.parcelles == ["35238000AB0297"]
    assert premiere.surface_habitable_totale == Decimal("80")
    assert premiere.nombre_locaux == 1
    assert premiere.prix_m2 == Decimal("1875")


async def test_mutations_nature_forcee_a_vente(depot):
    """Comportement actuel epingle, non approuve.

    `dvf/mapping.vers_mutations` selectionne `nature_mutation` puis l'ignore et
    ecrit `NatureMutation("Vente")` en dur. MUT011 est une adjudication dans la
    base et ressort en vente. Le test fige la conduite existante pour que la
    refonte ne la change pas par accident ; la corriger est une decision a part.
    """
    mutations = await depot.get_mutations_by_commune(COMMUNE)
    adjudication = next(m for m in mutations if m.id_mutation == "MUT011")
    assert adjudication.nature_mutation is NatureMutation.VENTE


async def test_mutations_filtre_intervalle_complet(depot):
    mutations = await depot.get_mutations_by_commune(
        COMMUNE, date_from=date(2023, 1, 1), date_to=date(2023, 12, 31)
    )
    assert [m.id_mutation for m in mutations] == ["MUT011"]


# --- get_price_stats -------------------------------------------------------


async def test_prix_stats_utilise_la_table_enrichie_et_exclut_les_outliers(depot):
    stats = await depot.get_price_stats(COMMUNE)

    # MUT099 (prix_m2 = 99000) est marquee is_outlier : elle ne doit pas peser.
    assert stats["min_price_m2"] == Decimal("2000")
    assert stats["max_price_m2"] == Decimal("4000")
    assert stats["avg_price_m2"] == Decimal("3000")
    assert stats["median_price_m2"] == Decimal("3000")


async def test_prix_stats_repli_sur_mutations_agregees(base_sans_enrichie):
    depot = DvfRepository(base_sans_enrichie)

    stats = await depot.get_price_stats(COMMUNE)

    # valeur / surface : 150000/80=1875, 200000/50=4000, 90000/30=3000
    assert stats["min_price_m2"] == Decimal("1875")
    assert stats["max_price_m2"] == Decimal("4000")


async def test_prix_stats_commune_sans_donnee_donne_zero(depot):
    stats = await depot.get_price_stats("99999")
    assert stats == {
        "min_price_m2": Decimal("0"),
        "max_price_m2": Decimal("0"),
        "median_price_m2": Decimal("0"),
        "avg_price_m2": Decimal("0"),
    }


# --- get_mutations_in_radius ----------------------------------------------


async def test_rayon_retourne_les_mutations_proches_triees(depot):
    mutations = await depot.get_mutations_in_radius(
        lat=48.1173, lon=-1.6778, radius_meters=2000
    )

    # MUT012 est a ~8 km : hors rayon. MUT013 est a ~515 m : dedans.
    assert [m.id_mutation for m in mutations] == ["MUT010", "MUT011", "MUT013"]
    assert mutations[0].longitude == pytest.approx(-1.6778)
    assert mutations[0].latitude == pytest.approx(48.1173)


async def test_rayon_exclut_au_dela(depot):
    mutations = await depot.get_mutations_in_radius(
        lat=48.1173, lon=-1.6778, radius_meters=100
    )
    assert [m.id_mutation for m in mutations] == ["MUT010"]


async def test_rayon_respecte_la_limite(depot):
    mutations = await depot.get_mutations_in_radius(
        lat=48.1173, lon=-1.6778, radius_meters=2000, limit=1
    )
    assert len(mutations) == 1


async def test_rayon_filtre_date_from_seule(depot):
    mutations = await depot.get_mutations_in_radius(
        lat=48.1173, lon=-1.6778, radius_meters=2000, date_from=date(2023, 1, 1)
    )
    assert [m.id_mutation for m in mutations] == ["MUT011", "MUT013"]


async def test_rayon_filtre_date_to_seule(depot):
    mutations = await depot.get_mutations_in_radius(
        lat=48.1173, lon=-1.6778, radius_meters=2000, date_to=date(2023, 1, 1)
    )
    assert [m.id_mutation for m in mutations] == ["MUT010"]


async def test_rayon_applique_les_deux_bornes_de_date(depot):
    """Les deux bornes ensemble doivent se cumuler.

    MUT010 (2022), MUT011 (2023) et MUT013 (2024) sont dans le rayon.
    L'intervalle 2023 ne doit garder que MUT011 : date_from ecarte MUT010,
    date_to ecarte MUT013. C'est cette seconde borne qui n'etait pas
    reellement sollicitee tant que le seul candidat tardif etait deja hors
    rayon.
    """
    mutations = await depot.get_mutations_in_radius(
        lat=48.1173,
        lon=-1.6778,
        radius_meters=2000,
        date_from=date(2023, 1, 1),
        date_to=date(2023, 12, 31),
    )
    assert [m.id_mutation for m in mutations] == ["MUT011"]


# --- get_parcelles_in_bbox -------------------------------------------------


async def test_parcelles_bbox_produit_un_geojson_valide(depot):
    brut = await depot.get_parcelles_in_bbox(
        min_x=-1.70, min_y=48.10, max_x=-1.65, max_y=48.13
    )
    collection = json.loads(brut)

    assert collection["type"] == "FeatureCollection"
    assert len(collection["features"]) == 3
    premiere = collection["features"][0]
    assert premiere["geometry"]["type"] == "Polygon"
    # Anneau ferme : premier point == dernier.
    anneau = premiere["geometry"]["coordinates"][0]
    assert anneau[0] == anneau[-1]


async def test_parcelles_bbox_porte_dpe_et_annee(depot):
    brut = await depot.get_parcelles_in_bbox(
        min_x=-1.70, min_y=48.10, max_x=-1.65, max_y=48.13
    )
    par_id = {
        f["properties"]["id"]: f["properties"]
        for f in json.loads(brut)["features"]
    }

    assert par_id["MUT010"]["dpe"] == "C"
    assert par_id["MUT010"]["annee"] == 1970
    # MUT099 a un DPE et une annee nuls : les cles sont omises, pas nulles.
    assert "dpe" not in par_id["MUT099"]
    assert "annee" not in par_id["MUT099"]


async def test_parcelles_bbox_respecte_la_limite(depot):
    brut = await depot.get_parcelles_in_bbox(
        min_x=-1.70, min_y=48.10, max_x=-1.65, max_y=48.13, limit=2
    )
    assert len(json.loads(brut)["features"]) == 2


async def test_parcelles_bbox_sans_table_enrichie_donne_collection_vide(
    base_sans_enrichie,
):
    depot = DvfRepository(base_sans_enrichie)

    brut = await depot.get_parcelles_in_bbox(
        min_x=-1.70, min_y=48.10, max_x=-1.65, max_y=48.13
    )

    assert json.loads(brut) == {"type": "FeatureCollection", "features": []}


# --- get_transactions_in_bbox (spatial) ------------------------------------


@requires_spatial
async def test_transactions_bbox_joint_les_parcelles(tmp_path):
    chemin = tmp_path / "dvf_spatial.duckdb"
    conn = duckdb.connect(str(chemin))
    conn.execute("INSTALL spatial; LOAD spatial;")
    _creer_tables(conn)
    conn.execute("""
        CREATE TABLE parcelles (id_parcelle VARCHAR, geometry GEOMETRY)
    """)
    conn.execute("""
        INSERT INTO parcelles VALUES
        ('35238000AB0297', ST_GeomFromText('POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))')),
        ('35238000AB0298', ST_GeomFromText('POLYGON((100 100, 110 100, 110 110, 100 110, 100 100))'))
    """)
    conn.close()

    try:
        depot = DvfRepository(chemin)
        transactions = await depot.get_transactions_in_bbox(-1, -1, 20, 20)
        assert [t.id_mutation for t in transactions] == ["MUT001"]
    finally:
        close_shared_connection(chemin)


# --- cycle de vie ----------------------------------------------------------


async def test_close_relache_la_connexion(base_dvf):
    depot = DvfRepository(base_dvf)
    await depot.get_transactions_by_commune(COMMUNE)

    depot.close()

    assert depot._conn is None
    # Reutilisable apres fermeture : la connexion est rouverte a la demande.
    assert await depot.get_transactions_by_commune(COMMUNE) != []
