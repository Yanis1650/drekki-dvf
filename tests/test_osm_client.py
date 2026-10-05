"""Tests du client OSM — le filet manquant avant refonte.

305 lignes sans test. Les trois methodes `fetch_*` interrogent Overpass via
OSMnx et ne se testent pas sans reseau ; en revanche le catalogue de tags et la
normalisation du GeoDataFrame sont purs, et ce sont eux qui portent les regles.

Le catalogue decide de ce que l'enrichissement va chercher : une categorie
perdue, et le score correspondant tombe a zero partout sans qu'aucune erreur ne
soit levee. La normalisation decide de ce qui en ressort : centroide, longitude,
latitude, sous-type.
"""

import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon

from app.infrastructure.osm_client import OsmClient, OsmPoiConfig, OsmTag

CATEGORIES = ("education", "transport", "transit", "nuisances", "commerce", "environnement")


# --- OsmPoiConfig ----------------------------------------------------------


def test_toutes_les_categories_sont_servies():
    """Une categorie vide ferait tomber son score a zero, en silence."""
    for categorie in CATEGORIES:
        assert OsmPoiConfig.get_tags_by_category(categorie), f"categorie vide : {categorie}"


def test_get_all_tags_reunit_exactement_les_six_categories():
    tous = OsmPoiConfig.get_all_tags()

    assert {t.category for t in tous} == set(CATEGORIES)
    attendu = sum(len(OsmPoiConfig.get_tags_by_category(c)) for c in CATEGORIES)
    assert len(tous) == attendu


def test_categorie_inconnue_donne_une_liste_vide():
    assert OsmPoiConfig.get_tags_by_category("chateaux") == []


def test_transit_et_transport_sont_deux_categories_distinctes():
    """Le transit suit une cloche TOD, le transport une decroissance simple.

    Les confondre reviendrait a noter une gare comme un arret de bus.
    """
    transit = {(t.key, t.value) for t in OsmPoiConfig.get_tags_by_category("transit")}
    transport = {(t.key, t.value) for t in OsmPoiConfig.get_tags_by_category("transport")}

    assert transit and transport
    assert transit.isdisjoint(transport)


def test_chaque_tag_declare_sa_categorie():
    for categorie in CATEGORIES:
        for tag in OsmPoiConfig.get_tags_by_category(categorie):
            assert tag.category == categorie


def test_to_osm_tags_dict_groupe_les_valeurs_par_cle():
    """Format attendu par OSMnx : une cle, la liste de ses valeurs."""
    tags = [
        OsmTag("amenity", "school", "education"),
        OsmTag("amenity", "library", "education"),
        OsmTag("railway", "station", "transit"),
    ]

    assert OsmPoiConfig.to_osm_tags_dict(tags) == {
        "amenity": ["school", "library"],
        "railway": ["station"],
    }


def test_to_osm_tags_dict_sur_liste_vide():
    assert OsmPoiConfig.to_osm_tags_dict([]) == {}


def test_le_catalogue_complet_est_convertible():
    resultat = OsmPoiConfig.to_osm_tags_dict(OsmPoiConfig.get_all_tags())

    assert resultat
    assert all(isinstance(v, list) and v for v in resultat.values())


# --- _process_gdf ----------------------------------------------------------


@pytest.fixture
def client():
    return OsmClient()


def test_normalisation_extrait_les_coordonnees(client):
    gdf = gpd.GeoDataFrame(
        {"amenity": ["school"], "name": ["Ecole Jules Ferry"]},
        geometry=[Point(-1.6778, 48.1173)],
        crs="EPSG:4326",
    )

    sortie = client._process_gdf(gdf, "education", OsmPoiConfig.get_tags_by_category("education"))

    assert sortie.iloc[0]["longitude"] == pytest.approx(-1.6778)
    assert sortie.iloc[0]["latitude"] == pytest.approx(48.1173)
    assert sortie.iloc[0]["category"] == "education"
    assert sortie.iloc[0]["sous_type"] == "school"
    assert sortie.iloc[0]["name"] == "Ecole Jules Ferry"


def test_un_polygone_est_ramene_a_son_centroide(client):
    """Un parc est une surface ; le score se calcule sur un point."""
    carre = Polygon([(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)])
    gdf = gpd.GeoDataFrame({"leisure": ["park"]}, geometry=[carre], crs="EPSG:4326")

    sortie = client._process_gdf(gdf, "environnement", OsmPoiConfig.get_tags_by_category("environnement"))

    assert sortie.iloc[0]["longitude"] == pytest.approx(1.0)
    assert sortie.iloc[0]["latitude"] == pytest.approx(1.0)


def test_sous_type_inconnu_quand_aucun_tag_ne_correspond(client):
    gdf = gpd.GeoDataFrame(
        {"amenity": ["fontaine_a_chats"]},
        geometry=[Point(0, 0)],
        crs="EPSG:4326",
    )

    sortie = client._process_gdf(gdf, "education", OsmPoiConfig.get_tags_by_category("education"))

    assert sortie.iloc[0]["sous_type"] == "unknown"


def test_colonne_name_ajoutee_si_absente(client):
    gdf = gpd.GeoDataFrame({"amenity": ["school"]}, geometry=[Point(0, 0)], crs="EPSG:4326")

    sortie = client._process_gdf(gdf, "education", OsmPoiConfig.get_tags_by_category("education"))

    assert "name" in sortie.columns
    assert sortie.iloc[0]["name"] is None


def test_seules_les_colonnes_utiles_sortent(client):
    gdf = gpd.GeoDataFrame(
        {"amenity": ["school"], "wikidata": ["Q42"], "source": ["cadastre"]},
        geometry=[Point(0, 0)],
        crs="EPSG:4326",
    )

    sortie = client._process_gdf(gdf, "education", OsmPoiConfig.get_tags_by_category("education"))

    assert set(sortie.columns) == {
        "name", "category", "sous_type", "longitude", "latitude", "geometry"
    }


def test_l_entree_n_est_pas_modifiee(client):
    """La normalisation travaille sur une copie : l'appelant garde son GeoDataFrame."""
    gdf = gpd.GeoDataFrame({"amenity": ["school"]}, geometry=[Point(3, 4)], crs="EPSG:4326")
    avant = list(gdf.columns)

    client._process_gdf(gdf, "education", OsmPoiConfig.get_tags_by_category("education"))

    assert list(gdf.columns) == avant
    assert gdf.iloc[0]["geometry"].x == 3
