"""Telechargement des PLU/PLUi depuis le WFS public GPU.

Trois etages : `client` (requete unitaire et troncature), `fetch` (les trois
couches, par partition), `build` (table doc_urba et GeoPackage). Le point
d'entree en ligne de commande reste `data-pipeline/download_plu_wfs.py`.
"""

from plu_wfs.build import build_doc_urba, save_gpkg
from plu_wfs.client import (
    APPROVED,
    ETAT_MAP,
    MAX_COUNT,
    RETRY_COUNT,
    TIMEOUT_S,
    WFS_BASE,
    WfsResult,
)
from plu_wfs.fetch import (
    fetch_commune_partition,
    fetch_doc_urba_for_partitions,
    fetch_zone_urba,
)

__all__ = [
    "APPROVED",
    "ETAT_MAP",
    "MAX_COUNT",
    "RETRY_COUNT",
    "TIMEOUT_S",
    "WFS_BASE",
    "WfsResult",
    "build_doc_urba",
    "fetch_commune_partition",
    "fetch_doc_urba_for_partitions",
    "fetch_zone_urba",
    "save_gpkg",
]
