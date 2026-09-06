"""Tests du depot POI et enrichissement — le filet manquant avant refonte.

231 lignes sans test. Trois des cinq methodes font de la geographie a la main :
une emprise rectangulaire pre-filtre, puis Haversine calcule la distance. Le
piege est connu — un rectangle n'est pas un disque, et son coin est a racine de
deux fois le rayon — et les trois methodes ne le traitent pas de la meme facon.
Ces tests le constatent, precisement pour que la refonte n'aligne pas les trois
par inadvertance.
"""

from decimal import Decimal

import duckdb
import pytest

from app.infrastructure.duckdb_pool import close_shared_connection
from app.repositories.poi_repository import PoiRepository

COMMUNE = "35238"
PARCELLE = "35238000AB0297"

# Rennes centre. Les distances sont calculees a cette latitude.
LAT, LON = 48.1173, -1.6778


@pytest.fixture
def base_poi(tmp_path):
    chemin = tmp_path / "poi.duckdb"
    conn = duckdb.connect(str(chemin))
    conn.execute("""
        CREATE TABLE points_interet (
            id VARCHAR, nom VARCHAR, type_poi VARCHAR, sous_type VARCHAR,
            longitude DOUBLE, latitude DOUBLE, code_commune VARCHAR,
            code_postal VARCHAR
        )
    """)
    # Distances approximatives depuis (48.1173, -1.6778) :
    #   P1 ecole      ~   0 m
    #   P2 ecole      ~ 340 m
    #   P3 gare       ~ 170 m
    #   P4 ecole      ~ 8 km  (hors de toute emprise testee)
    conn.execute(f"""
        INSERT INTO points_interet VALUES
        ('P1', 'Ecole Jules Ferry', 'ecole', 'elementaire', {LON}, {LAT}, '{COMMUNE}', '35000'),
        ('P2', 'Ecole Victor Hugo', 'ecole', 'maternelle', -1.6800, 48.1200, '{COMMUNE}', '35000'),
        ('P3', 'Gare de Rennes', 'gare', 'ter', -1.6760, 48.1160, '{COMMUNE}', '35000'),
        ('P4', 'Ecole lointaine', 'ecole', 'college', {LON}, 48.1900, '{COMMUNE}', '35000')
    """)
    conn.execute("""
        CREATE TABLE enrichment_scores (
            id_parcelle VARCHAR, schools_score DOUBLE, transport_score DOUBLE,
            nuisances_score DOUBLE, green_spaces_score DOUBLE
        )
    """)
    # get_enrichments_by_commune joint `parcelles` : c'est elle qui porte la commune.
    conn.execute("""
        CREATE TABLE parcelles (id_parcelle VARCHAR, code_commune VARCHAR)
    """)
    conn.execute(f"""
        INSERT INTO parcelles VALUES
        ('{PARCELLE}', '{COMMUNE}'),
        ('35238000AB0298', '{COMMUNE}'),
        ('35047000AB0001', '35047')
    """)
    conn.execute(f"""
        INSERT INTO enrichment_scores VALUES
        ('{PARCELLE}', 8.0, 6.5, 3.0, 7.0),
        ('35238000AB0298', 5.0, 5.0, 5.0, 5.0),
        ('35047000AB0001', 2.0, 2.0, 2.0, 2.0)
    """)
    conn.close()
    yield chemin
    close_shared_connection(chemin)


@pytest.fixture
def depot(base_poi):
    return PoiRepository(base_poi)


# --- scores d'enrichissement -----------------------------------------------


async def test_score_par_parcelle(depot):
    score = await depot.get_enrichment_by_parcelle(PARCELLE)

    assert score.id_parcelle == PARCELLE
    assert score.schools_score == Decimal("8.0")
    assert score.transport_score == Decimal("6.5")
    assert score.nuisances_score == Decimal("3.0")
    assert score.green_spaces_score == Decimal("7.0")


async def test_transit_et_commerce_gardent_leur_defaut(depot):
    """Ces deux composantes ne sont pas stockees : le modele les met a 5.

    transit_score se recalcule a la volee (cloche TOD) ; le lire ici comme une
    mesure serait une erreur.
    """
    score = await depot.get_enrichment_by_parcelle(PARCELLE)

    assert score.transit_score == Decimal("5.0")
    assert score.commerce_score == Decimal("5.0")


async def test_parcelle_inconnue_donne_none(depot):
    assert await depot.get_enrichment_by_parcelle("35999000ZZ9999") is None


async def test_scores_par_commune(depot):
    scores = await depot.get_enrichments_by_commune(COMMUNE)

    assert {s.id_parcelle for s in scores} == {PARCELLE, "35238000AB0298"}


async def test_commune_sans_score_donne_liste_vide(depot):
    assert await depot.get_enrichments_by_commune("99999") == []


# --- comptage dans un rayon ------------------------------------------------


async def test_comptage_toutes_categories(depot):
    """P1, P2 et P3 sont dans l'emprise ; P4 est a 8 km."""
    assert await depot.get_poi_count_in_radius(LAT, LON, 1000) == 3


async def test_comptage_filtre_par_type(depot):
    assert await depot.get_poi_count_in_radius(LAT, LON, 1000, type_poi="ecole") == 2
    assert await depot.get_poi_count_in_radius(LAT, LON, 1000, type_poi="gare") == 1


async def test_comptage_type_inexistant(depot):
    assert await depot.get_poi_count_in_radius(LAT, LON, 1000, type_poi="aeroport") == 0


async def test_comptage_rayon_etroit(depot):
    assert await depot.get_poi_count_in_radius(LAT, LON, 50) == 1


# --- plus proche POI -------------------------------------------------------


async def test_plus_proche_ecole(depot):
    poi = await depot.get_nearest_poi(LAT, LON, "ecole")

    assert poi["id"] == "P1"
    assert poi["nom"] == "Ecole Jules Ferry"
    assert poi["distance_m"] == pytest.approx(0, abs=1)


async def test_plus_proche_respecte_le_type(depot):
    poi = await depot.get_nearest_poi(LAT, LON, "gare")

    assert poi["id"] == "P3"


async def test_plus_proche_type_absent_donne_none(depot):
    assert await depot.get_nearest_poi(LAT, LON, "aeroport") is None


async def test_plus_proche_hors_emprise_donne_none(depot):
    """P4 est a 8 km : une emprise de 100 m ne l'atteint pas."""
    assert await depot.get_nearest_poi(LAT, LON, "college", max_distance_m=100) is None


async def test_plus_proche_ne_borne_pas_sur_la_distance_reelle(depot):
    """Comportement actuel epingle, non approuve.

    `get_nearest_poi` pre-filtre sur une emprise rectangulaire mais ne verifie
    jamais `distance_m <= max_distance_m`. Un POI situe dans un coin du
    rectangle ressort donc alors qu'il est au-dela du rayon demande — jusqu'a
    racine de deux fois celui-ci.

    `get_poi_in_radius`, lui, applique bien la borne. Les deux methodes ne
    traitent donc pas le meme probleme de la meme facon ; le test fige l'ecart
    pour que la refonte ne le referme pas sans decision explicite.
    """
    # P2 est a ~340 m. Une emprise de 300 m le contient en diagonale.
    poi = await depot.get_nearest_poi(LAT + 0.0027, LON - 0.0022, "ecole", max_distance_m=300)

    assert poi is not None
    assert poi["id"] == "P2"


# --- POI dans un rayon -----------------------------------------------------


async def test_poi_dans_un_rayon_tries_par_distance(depot):
    poi = await depot.get_poi_in_radius(LAT, LON, 1000)

    assert [p["id"] for p in poi] == ["P1", "P3", "P2"]
    assert poi[0]["distance_m"] <= poi[1]["distance_m"] <= poi[2]["distance_m"]


async def test_poi_dans_un_rayon_borne_bien_la_distance(depot):
    """Contrairement a get_nearest_poi, celui-ci applique distance_m <= rayon."""
    poi = await depot.get_poi_in_radius(LAT, LON, 200)

    assert [p["id"] for p in poi] == ["P1", "P3"]


async def test_poi_dans_un_rayon_ecarte_les_coins_de_l_emprise(depot):
    """Le test qui sollicite reellement la borne de distance.

    A 320 m de rayon, l'emprise rectangulaire contient P2 (300 m au nord,
    163 m a l'ouest) alors que sa distance reelle vaut ~341 m. Seule la clause
    `distance_m <= rayon` l'ecarte. Avec un rayon plus etroit, l'emprise
    l'excluait deja et la clause n'etait jamais mise a l'epreuve — un test vert
    qui ne prouvait rien.
    """
    poi = await depot.get_poi_in_radius(LAT, LON, 320)

    assert "P2" not in [p["id"] for p in poi]
    assert {p["id"] for p in poi} == {"P1", "P3"}


async def test_poi_dans_un_rayon_filtre_par_type(depot):
    poi = await depot.get_poi_in_radius(LAT, LON, 1000, type_poi="ecole")

    assert {p["id"] for p in poi} == {"P1", "P2"}


async def test_poi_dans_un_rayon_respecte_la_limite(depot):
    poi = await depot.get_poi_in_radius(LAT, LON, 1000, limit=2)

    assert len(poi) == 2


# --- cycle de vie ----------------------------------------------------------


async def test_close_relache_la_connexion(base_poi):
    depot = PoiRepository(base_poi)
    await depot.get_enrichment_by_parcelle(PARCELLE)

    depot.close()

    assert depot._conn is None
    assert await depot.get_enrichment_by_parcelle(PARCELLE) is not None
