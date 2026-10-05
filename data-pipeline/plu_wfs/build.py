"""Construction de la table doc_urba et ecriture du GeoPackage."""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
from plu_wfs.client import ETAT_MAP

logger = logging.getLogger(__name__)


def build_doc_urba(
    df_commune_partition: pd.DataFrame, gdf_doc_raw: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """
    Construit la table doc_urba avec le champ 'code_commune' requis par import_plu.py.

    Une ligne **par commune**, pas par partition : `import_plu.py` en dérive
    directement `plu_commune_partition`. Un PLUi couvrant 43 communes doit donc
    produire 43 lignes — les réduire à une seule (ce que faisait un
    `groupby('partition').first()` sur `zone_urba.insee`) rattachait le document
    à une commune arbitraire et laissait les 42 autres sans PLU.
    """
    if df_commune_partition.empty:
        return gpd.GeoDataFrame()

    zone_part = df_commune_partition.drop_duplicates()

    if not gdf_doc_raw.empty:
        meta_cols = [c for c in
                     ["partition", "idurba", "typedoc", "datappro", "etat",
                      "siren", "interco", "geometry"]
                     if c in gdf_doc_raw.columns]
        doc_meta = gdf_doc_raw[meta_cols].drop_duplicates(subset=["partition"])

        # Traduction codes numériques GPU → libellés import_plu.py
        if "etat" in doc_meta.columns:
            doc_meta = doc_meta.copy()
            doc_meta["etat"] = doc_meta["etat"].map(
                lambda v: ETAT_MAP.get(str(v), str(v)) if pd.notna(v) else None
            )
        result = zone_part.merge(doc_meta, on="partition", how="left")
    else:
        result = zone_part

    return gpd.GeoDataFrame(
        result,
        geometry="geometry" if "geometry" in result.columns else None,
    )


def save_gpkg(gdf_doc: gpd.GeoDataFrame, gdf_zones: gpd.GeoDataFrame, out: Path) -> None:
    """Ecrit les deux couches en Lambert-93, layer par layer."""
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    def _l93(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        if gdf.empty or gdf.geometry is None or gdf.crs is None:
            return gdf
        try:
            return gdf.to_crs("EPSG:2154")
        except Exception as e:
            logger.warning("Reprojection impossible: %s", e)
            return gdf

    if not gdf_doc.empty:
        _l93(gdf_doc).to_file(out, layer="doc_urba", driver="GPKG")
        print(f"  Layer doc_urba  : {len(gdf_doc):,} partitions -> {out.name}")

    if not gdf_zones.empty:
        _l93(gdf_zones).to_file(out, layer="zone_urba", driver="GPKG")
        print(f"  Layer zone_urba : {len(gdf_zones):,} zones -> {out.name}")
