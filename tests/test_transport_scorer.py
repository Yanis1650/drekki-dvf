"""Tests du scoreur transport — le filet manquant avant de changer sa requete.

`TransportScorer` n'avait aucun test. Sa requete filtrait `type_poi = 'gare'`,
valeur qu'ecrivait `etl_poi.py` — l'ETL a donnees aleatoires supprime de ce
depot. Le seul chargeur restant, `etl_osm_enrichment.py`, ecrit `'transport'`
et `'transit'` : sur de vraies donnees, le score sortait a zero. Ces tests ont
d'abord constate le bareme — cinq paliers de distance, deux bonus et leurs
plafonds — pour que le deplacement vers le vocabulaire OSM ne le touche pas.
Seul le vocabulaire interroge a change.

Les distances sont posees en latitude pure, avec le rayon terrestre du scoreur
lui-meme (6 371 km) : une erreur de conversion se verrait sur `nearest_distance_m`
avant de fausser un palier.
"""

import math
from decimal import Decimal
from itertools import count

import duckdb
import pytest

from app.services.enrichment.transport_scorer import TransportScorer

# Rennes centre.
LAT, LON = 48.1173, -1.6778

# Metres par degre de latitude, au rayon utilise par le scoreur.
M_PAR_DEG = 6371000 * math.radians(1)

# Le vocabulaire que la requete reconnait. La table en porte d'autres, que le
# scoreur doit ignorer : c'est le sens du test `ecole_ignoree`.
TYPE_TROUVE = "transit"


def latitude_a(metres: float) -> float:
    """Latitude situee `metres` au nord de LAT, a longitude constante."""
    return LAT + metres / M_PAR_DEG


def longitude_a(metres: float) -> float:
    """Longitude situee `metres` a l'est de LON, a latitude constante."""
    return LON + metres / (M_PAR_DEG * math.cos(math.radians(LAT)))


@pytest.fixture
def base(tmp_path):
    """Fabrique une base au schema de `etl_osm_enrichment.py`.

    Prend une liste de `(type_poi, sous_type, distance_en_metres)` et rend le
    scoreur pointe dessus.
    """

    numero = count()

    def fabriquer(lignes, avec_table=True, diagonales=()):
        chemin = tmp_path / f"poi_{next(numero)}.duckdb"
        conn = duckdb.connect(str(chemin))
        if not avec_table:
            conn.execute("CREATE TABLE autre_chose (x INTEGER)")
            conn.close()
            return TransportScorer(duckdb_path=chemin)
        conn.execute("""
            CREATE TABLE points_interet (
                id VARCHAR, nom VARCHAR, type_poi VARCHAR, sous_type VARCHAR,
                longitude DOUBLE, latitude DOUBLE, code_commune VARCHAR,
                source VARCHAR
            )
        """)
        for i, (type_poi, sous_type, metres) in enumerate(lignes):
            conn.execute(
                "INSERT INTO points_interet VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [f"P{i}", f"POI {i}", type_poi, sous_type, LON,
                 latitude_a(metres), "35238", "osm"],
            )
        for i, (type_poi, sous_type, nord, est) in enumerate(diagonales):
            conn.execute(
                "INSERT INTO points_interet VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [f"D{i}", f"POI diagonal {i}", type_poi, sous_type,
                 longitude_a(est), latitude_a(nord), "35238", "osm"],
            )
        conn.close()
        return TransportScorer(duckdb_path=chemin)

    return fabriquer


# --- Les cinq paliers de distance -------------------------------------------
#
# Une seule station, donc bonus de comptage constant (0,3 en deca de 1 km, 0
# au-dela) et bonus de diversite constant (0,15). Le palier est la seule
# variable, et les valeurs attendues portent ses arrondis tels qu'ils sortent.


@pytest.mark.parametrize(("metres", "attendu"), [
    (150, "8.5"),    # palier 8 : <= 200 m
    (400, "6.4"),    # palier 6 : <= 500 m
    (900, "4.4"),    # palier 4 : <= 1000 m
    (1400, "2.2"),   # palier 2 : <= 1500 m — hors du bonus de comptage
    (1900, "1.2"),   # palier 1 : au-dela
])
async def test_paliers_de_distance(base, metres, attendu):
    scoreur = base([(TYPE_TROUVE, "ter", metres)])

    details = await scoreur.calculate_score_with_details(LAT, LON)

    assert details["score"] == Decimal(attendu), (
        f"a {metres} m, score attendu {attendu}, obtenu {details['score']}"
    )
    assert details["nearest_distance_m"] == metres


async def test_arrondis_incoherents_figes_sans_etre_approuves(base):
    """8,45 monte a 8,5 mais 6,45 descend a 6,4.

    `Decimal.quantize` arrondit au pair le plus proche, et le flottant qui le
    precede tombe tantot au-dessus, tantot en dessous de la demie. Deux paliers
    voisins arrondissent donc dans des sens opposes. Ce test fige ce
    comportement pour qu'un changement de bareme le fasse remarquer — il ne
    l'approuve pas.
    """
    a_150 = await base([(TYPE_TROUVE, "ter", 150)]).calculate_score_with_details(LAT, LON)
    a_400 = await base([(TYPE_TROUVE, "ter", 400)]).calculate_score_with_details(LAT, LON)

    assert a_150["score"] == Decimal("8.5")   # 8 + 0,3 + 0,15 = 8,45 -> 8,5
    assert a_400["score"] == Decimal("6.4")   # 6 + 0,3 + 0,15 = 6,45 -> 6,4


# --- Les deux bonus et leurs plafonds ---------------------------------------


async def test_bonus_de_comptage_plafonne_a_1_5(base):
    """Six stations valent 1,5 de bonus, pas 6 x 0,3 = 1,8."""
    scoreur = base([
        (TYPE_TROUVE, "ter", d) for d in (100, 200, 300, 400, 500, 600)
    ])

    details = await scoreur.calculate_score_with_details(LAT, LON)

    assert details["stations_1km"] == 6
    # 8 (palier) + 1,5 (plafond) + 0,15 (diversite) = 9,65, arrondi a 9,6
    assert details["score"] == Decimal("9.6")


async def test_bonus_de_diversite_plafonne_a_0_5(base):
    """Quatre sous-types valent 0,5, pas 4 x 0,15 = 0,6."""
    scoreur = base([
        (TYPE_TROUVE, sous_type, 150 + i)
        for i, sous_type in enumerate(("ter", "metro", "tram", "bus"))
    ])

    details = await scoreur.calculate_score_with_details(LAT, LON)

    assert sorted(details["transport_types"]) == ["bus", "metro", "ter", "tram"]
    assert details["score"] == Decimal("9.7")


# --- Les deux bornes --------------------------------------------------------


async def test_hors_de_l_emprise_rectangulaire_score_nul(base):
    """A 3 km plein nord, l'emprise ecarte la station avant tout calcul."""
    scoreur = base([(TYPE_TROUVE, "ter", 3000)])

    details = await scoreur.calculate_score_with_details(LAT, LON)

    assert details["score"] == Decimal("0.0")
    assert details["nearest_distance_m"] is None
    assert details["stations_1km"] == 0
    assert details["transport_types"] == []


async def test_station_a_l_est_trouvee_malgre_la_convergence_des_meridiens(base):
    """A 48 degres de latitude, un degre de longitude ne vaut que 74 km.

    L'emprise divise donc le demi-cote est-ouest par `111000 * cos(lat)`. Sans
    ce facteur, elle se retrecirait a 1 334 m d'est en ouest et manquerait
    cette station posee a 1 400 m plein est — pourtant bien dans le disque de
    2 km. Le cas est a l'est precisement parce que tous les autres sont au nord,
    ou le facteur n'intervient pas.
    """
    scoreur = base([], diagonales=[(TYPE_TROUVE, "ter", 0, 1400)])

    details = await scoreur.calculate_score_with_details(LAT, LON)

    assert details["nearest_distance_m"] == 1400
    assert details["score"] == Decimal("2.2")


async def test_dans_l_emprise_mais_au_dela_de_2km_score_nul(base):
    """La clause de distance, et non l'emprise, ecarte le coin du rectangle.

    L'emprise est un rectangle de 2 km de demi-cote ; son coin est a racine de
    deux fois cette distance, soit 2 828 m. Une station a 1 800 m au nord et
    1 800 m a l'est y tient (2 546 m du centre) alors qu'elle est hors du
    disque de 2 km. Sans ce cas, un elargissement du rayon passerait inapercu :
    tout ce qui est pose plein nord au-dela de 2 km est deja hors de l'emprise.
    """
    scoreur = base([], diagonales=[(TYPE_TROUVE, "ter", 1800, 1800)])

    details = await scoreur.calculate_score_with_details(LAT, LON)

    assert details["score"] == Decimal("0.0")
    assert details["nearest_distance_m"] is None


async def test_ecole_ignoree(base):
    """Un POI d'un autre type, au meme endroit, ne compte pas."""
    scoreur = base([("ecole", "elementaire", 150)])

    details = await scoreur.calculate_score_with_details(LAT, LON)

    assert details["score"] == Decimal("0.0")


async def test_table_absente_rend_5_sur_10_fige_sans_etre_approuve(base):
    """Sans table `points_interet`, le scoreur rend 5,0 — une valeur inventee.

    `docs/PIPELINE.md` promet l'inverse : « scores omis, jamais remplaces par
    5/10 ». La promesse tient au niveau du service, qui interroge
    `data_availability` avant d'appeler un scoreur ; elle ne tient pas ici. Ce
    test fige l'ecart pour qu'il reste visible, il ne l'approuve pas.
    """
    scoreur = base([], avec_table=False)

    details = await scoreur.calculate_score_with_details(LAT, LON)

    assert details["score"] == Decimal("5.0")
    assert "error" in details


# --- Le vocabulaire interroge -----------------------------------------------


async def test_gare_ferroviaire_osm_trouvee(base):
    """`etl_osm_enrichment.py` classe les gares, metros et trams en `transit`."""
    scoreur = base([("transit", "station", 150)])

    details = await scoreur.calculate_score_with_details(LAT, LON)

    assert details["score"] > Decimal("0"), (
        "une gare chargee par le seul ETL a vraies donnees doit compter"
    )
    assert details["nearest_distance_m"] == 150


async def test_arret_de_bus_osm_trouve(base):
    """Le meme ETL classe bus, gares routieres et velos en `transport`."""
    scoreur = base([("transport", "bus_stop", 150)])

    details = await scoreur.calculate_score_with_details(LAT, LON)

    assert details["score"] > Decimal("0")
    assert details["nearest_distance_m"] == 150


async def test_vocabulaire_gare_de_l_etl_supprime_ignore(base):
    """`'gare'` ne venait que de `etl_poi.py`, retire de ce depot.

    Une base anterieure peut en porter encore ; le scoreur ne les compte plus.
    Repeupler `points_interet` par `etl_osm_enrichment.py` restitue les scores.
    """
    scoreur = base([("gare", "ter", 150)])

    details = await scoreur.calculate_score_with_details(LAT, LON)

    assert details["score"] == Decimal("0.0")
