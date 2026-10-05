"""Client WFS GPU : requete unitaire, detection de troncature, conversion.

WFS public : https://data.geopf.fr/wfs/ows

Note technique : `startIndex` n'est PAS supporte par ce serveur (HTTP 400).
La seule facon de recuperer un jeu tronque est de redecouper le filtre, ce
que fait `plu_wfs.fetch`.
"""

from __future__ import annotations

import logging
import time
from typing import NamedTuple

import geopandas as gpd
import requests
from shapely.geometry import shape

logger = logging.getLogger(__name__)

WFS_BASE    = "https://data.geopf.fr/wfs/ows"
MAX_COUNT   = 9999     # compte maximum par requête (startIndex non supporté)
TIMEOUT_S   = 90
RETRY_COUNT = 3
APPROVED    = {"Approuvé", "Opposable", "Applicable", "En vigueur"}

# Codes numériques GPU → libellés attendus par import_plu.py
ETAT_MAP: dict[str, str] = {
    "01": "En cours d'elaboration",
    "02": "En cours de revision",
    "03": "Opposable",
    "04": "Caduc",
    "05": "Annule",
    "06": "En cours d'instruction",
    "07": "Applicable",
    "08": "En vigueur",
}


class WfsResult(NamedTuple):
    """Réponse WFS et son état de complétude.

    Le serveur GPU plafonne ses réponses (5 000 features observées) et le
    signale en renvoyant `numberReturned` < `numberMatched`. Comparer le nombre
    de features au `count` demandé ne détecte pas ce cas : c'est ainsi que
    4 627 zones du PLUi de Rennes disparaissaient sans le moindre message.
    """

    features: list[dict]
    matched: int      # nombre total de features correspondant au filtre
    returned: int     # nombre effectivement renvoyé

    @property
    def truncated(self) -> bool:
        """True si le serveur a tronqué la réponse."""
        return self.matched > self.returned


def _wfs_get(typename: str, cql_filter: str, count: int = MAX_COUNT) -> WfsResult:
    """
    Effectue une requête WFS GetFeature.

    Important : startIndex n'est pas supporté par ce WFS. La seule façon de
    récupérer un jeu tronqué est de redécouper le filtre — voir `WfsResult`.
    """
    params = {
        "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
        "TYPENAMES": typename, "outputFormat": "application/json",
        "count": count, "CQL_FILTER": cql_filter,
    }
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            r = requests.get(WFS_BASE, params=params, timeout=TIMEOUT_S)
            r.raise_for_status()
            payload = r.json()
            feats = payload.get("features", [])
            matched = payload.get("numberMatched")
            returned = payload.get("numberReturned")
            return WfsResult(
                features=feats,
                matched=int(matched) if matched is not None else len(feats),
                returned=int(returned) if returned is not None else len(feats),
            )
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 400:
                # 400 = filtre invalide ou startIndex utilisé, ne pas retenter
                raise
            if attempt == RETRY_COUNT:
                raise
        except requests.exceptions.RequestException:
            if attempt == RETRY_COUNT:
                raise
        logger.warning("Tentative %d/%d pour %s", attempt, RETRY_COUNT, typename)
        time.sleep(2 * attempt)
    return WfsResult([], 0, 0)


def _to_gdf(features: list[dict], crs: str = "EPSG:4326") -> gpd.GeoDataFrame:
    """Features GeoJSON du WFS vers GeoDataFrame."""
    if not features:
        return gpd.GeoDataFrame()
    rows = []
    for f in features:
        props = dict(f.get("properties") or {})
        geom_raw = f.get("geometry")
        props["geometry"] = shape(geom_raw) if geom_raw else None
        rows.append(props)
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=crs)
