"""Tests du téléchargement PLU depuis le WFS GPU.

Deux pièges silencieux ont coûté 95 % des zones du département 35 :

1. filtrer `zone_urba` sur `insee`, champ quasi vide dans cette couche
   (1 018 zones au lieu de 22 235) ;
2. ne pas voir que le serveur tronque ses réponses à 5 000 features — la
   comparaison au `count` demandé (9 999) ne détectait rien, et le PLUi de
   Rennes perdait 4 627 zones sans un seul message.

Ces tests verrouillent les deux comportements sans toucher le réseau.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "data-pipeline"))

from conftest import stub_missing_modules  # noqa: E402

stub_missing_modules(
    "geopandas", "fiona", "pyogrio", "shapely", "shapely.geometry",
    "shapely.validation", "shapely.ops", "shapely.strtree", "owslib", "owslib.wfs",
    "owslib.util", "pyproj", "pyproj.transformer", "requests", "osmnx", "networkx",
    "polars", "polars.exceptions", "polars.selectors", "aiohttp", "rtree",
)

import download_plu_wfs as dl  # noqa: E402


def _feature(gid: str, partition: str) -> dict:
    return {"id": gid, "properties": {"gid": gid, "partition": partition}, "geometry": None}


class TestWfsResultTruncation:
    """`numberReturned` < `numberMatched` est le seul signal fiable."""

    def test_reponse_complete_non_tronquee(self):
        res = dl.WfsResult(features=[], matched=4069, returned=4069)
        assert res.truncated is False

    def test_reponse_plafonnee_detectee(self):
        # Cas réel : lot de 20 partitions, serveur plafonné à 5000.
        res = dl.WfsResult(features=[], matched=9627, returned=5000)
        assert res.truncated is True

    def test_troncature_invisible_pour_l_ancienne_heuristique(self):
        """L'ancien test `len(feats) >= MAX_COUNT` laissait passer ce cas."""
        res = dl.WfsResult(features=[], matched=9627, returned=5000)
        assert res.returned < dl.MAX_COUNT, "l'ancienne heuristique ne voyait rien"
        assert res.truncated is True, "la nouvelle detection doit voir la troncature"


class TestFetchZoneUrba:
    """Le découpage doit rattraper les lots tronqués."""

    def test_lot_complet_pas_de_redecoupage(self):
        calls = []

        def fake(typename, cql, count=None):
            calls.append(cql)
            return dl.WfsResult([_feature("1", "DU_35001")], matched=1, returned=1)

        with patch.object(dl, "_wfs_get", side_effect=fake), \
             patch.object(dl, "_to_gdf", side_effect=lambda f: f), \
             patch.object(dl.time, "sleep"):
            dl.fetch_zone_urba(["DU_35001"], batch_size=20)

        assert len(calls) == 1, "un lot complet ne doit pas etre redecoupe"
        assert "partition IN" in calls[0]

    def test_lot_tronque_redecoupe_par_partition(self):
        parts = ["DU_A", "DU_B", "DU_C"]
        calls = []

        def fake(typename, cql, count=None):
            calls.append(cql)
            if "IN (" in cql:
                # Le serveur tronque le lot.
                return dl.WfsResult([_feature("x", "DU_A")], matched=9627, returned=5000)
            part = cql.split("'")[1]
            return dl.WfsResult([_feature(f"g-{part}", part)], matched=1, returned=1)

        with patch.object(dl, "_wfs_get", side_effect=fake), \
             patch.object(dl, "_to_gdf", side_effect=lambda f: f), \
             patch.object(dl.time, "sleep"):
            feats = dl.fetch_zone_urba(parts, batch_size=20)

        assert len(calls) == 1 + len(parts), "chaque partition doit etre reprise seule"
        gids = {f["properties"]["gid"] for f in feats}
        assert gids == {"g-DU_A", "g-DU_B", "g-DU_C"}

    def test_ne_filtre_jamais_sur_insee(self):
        """Le filtre `insee` est le piège d'origine : il ne doit plus exister."""
        calls = []

        def fake(typename, cql, count=None):
            calls.append(cql)
            return dl.WfsResult([], matched=0, returned=0)

        with patch.object(dl, "_wfs_get", side_effect=fake), \
             patch.object(dl, "_to_gdf", side_effect=lambda f: f), \
             patch.object(dl.time, "sleep"):
            dl.fetch_zone_urba(["DU_35001", "DU_243500139"], batch_size=20)

        assert calls, "une requete doit partir"
        assert all("insee" not in c for c in calls)
        assert all("partition" in c for c in calls)


class TestBuildDocUrba:
    """doc_urba doit compter une ligne par commune, PLUi compris."""

    def test_plui_produit_une_ligne_par_commune(self):
        """43 communes sous un même PLUi = 43 lignes, pas une seule.

        Un `groupby('partition').first()` n'en gardait qu'une : les 42 autres
        se retrouvaient sans PLU et retombaient sur le fallback RNU.
        """
        df_cp = pd.DataFrame([
            {"code_commune": "35238", "partition": "DU_243500139"},
            {"code_commune": "35278", "partition": "DU_243500139"},
            {"code_commune": "35131", "partition": "DU_243500139"},
            {"code_commune": "35101", "partition": "DU_35101"},
        ])
        empty = pd.DataFrame()

        with patch.object(dl.gpd, "GeoDataFrame", side_effect=lambda d, **k: d):
            out = dl.build_doc_urba(df_cp, empty)

        assert len(out) == 4
        assert (out["partition"] == "DU_243500139").sum() == 3

    def test_mapping_vide_renvoie_vide(self):
        with patch.object(dl.gpd, "GeoDataFrame", return_value=pd.DataFrame()):
            out = dl.build_doc_urba(pd.DataFrame(), pd.DataFrame())
        assert len(out) == 0


class TestFetchCommunePartition:
    """Le mapping vient de doc_urba_com, seule couche qui porte les PLUi."""

    def test_utilise_doc_urba_com(self):
        seen = {}

        def fake(typename, cql, count=None):
            seen["typename"] = typename
            seen["cql"] = cql
            return dl.WfsResult(
                [{"properties": {"insee": "35238", "partition": "DU_243500139"}}],
                matched=1, returned=1,
            )

        with patch.object(dl, "_wfs_get", side_effect=fake):
            df = dl.fetch_commune_partition("35")

        assert seen["typename"] == "wfs_du:doc_urba_com"
        assert "insee LIKE '35%'" in seen["cql"]
        assert df.iloc[0]["partition"] == "DU_243500139"

    def test_troncature_signalee(self, caplog):
        def fake(typename, cql, count=None):
            return dl.WfsResult([], matched=500, returned=200)

        with patch.object(dl, "_wfs_get", side_effect=fake):
            with caplog.at_level("WARNING"):
                dl.fetch_commune_partition("35")

        assert any("tronque" in r.message.lower() for r in caplog.records)


@pytest.mark.parametrize("matched,returned,expected", [
    (0, 0, False),
    (100, 100, False),
    (5001, 5000, True),
    (22235, 5000, True),
])
def test_truncated_table(matched, returned, expected):
    assert dl.WfsResult([], matched, returned).truncated is expected
