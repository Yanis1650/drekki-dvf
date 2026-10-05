"""Telechargement des couches GPU, par partition.

**Ne jamais filtrer zone_urba sur `insee`.** Ce champ est très majoritairement
vide dans la couche : sur le département 35, `insee LIKE '35%'` renvoie 1 018
zones là où le filtre par partition en renvoie 22 235 — soit 95 % des zones
perdues en silence. C'est ce qui avait fait conclure à tort que le PLUi de
Rennes Métropole n'était pas publié sur le WFS : ses 4 069 zones y sont, sous
la partition `DU_243500139`, mais sans `insee` renseigné.

Le mapping commune ↔ partition vient donc de `doc_urba_com`, seule source qui
rattache correctement une commune à un document intercommunal.
"""

from __future__ import annotations

import logging
import time

import geopandas as gpd
import pandas as pd
from plu_wfs.client import MAX_COUNT, _to_gdf, _wfs_get

logger = logging.getLogger(__name__)


def fetch_commune_partition(dept: str) -> pd.DataFrame:
    """Récupère le lien commune ↔ document depuis `doc_urba_com`.

    C'est la seule source qui rattache correctement une commune à un document
    intercommunal : un PLUi porte une partition `DU_<SIREN_EPCI>`, qu'aucun
    filtre sur le code département ne peut retrouver.

    Returns:
        DataFrame à deux colonnes : code_commune, partition.
    """
    res = _wfs_get("wfs_du:doc_urba_com", f"insee LIKE '{dept}%'", count=MAX_COUNT)
    if res.truncated:
        logger.warning(
            "doc_urba_com tronque (%d/%d) — mapping incomplet pour le dept %s",
            res.returned, res.matched, dept,
        )
    rows = [
        {"code_commune": p.get("insee"), "partition": p.get("partition")}
        for p in (f.get("properties") or {} for f in res.features)
        if p.get("insee") and p.get("partition")
    ]
    return pd.DataFrame(rows).drop_duplicates()


def fetch_zone_urba(partitions: list[str], batch_size: int = 20) -> gpd.GeoDataFrame:
    """Récupère les zones PLU des partitions données, par lots.

    Le filtre porte sur `partition`, jamais sur `insee` : voir l'avertissement
    en tête de module. Un lot qui atteint le plafond de features est redécoupé
    partition par partition, sinon on perdrait silencieusement des zones.
    """
    if not partitions:
        return gpd.GeoDataFrame()

    all_features: list[dict] = []
    seen_gids: set = set()
    incomplete: list[str] = []

    def _collect(feats: list[dict]) -> None:
        for f in feats:
            gid = f.get("id") or (f.get("properties") or {}).get("gid")
            if gid not in seen_gids:
                seen_gids.add(gid)
                all_features.append(f)

    def _fetch_one(part: str) -> None:
        """Récupère une partition seule ; signale si elle reste tronquée."""
        try:
            res = _wfs_get("wfs_du:zone_urba", f"partition='{part}'", count=MAX_COUNT)
        except Exception as exc:
            logger.warning("Partition %s echouee: %s", part, exc)
            incomplete.append(part)
            return
        if res.truncated:
            # Une partition seule dépasse le plafond serveur : sans startIndex,
            # on ne peut pas aller plus loin. On le dit plutôt que de laisser
            # croire à un import complet.
            logger.error(
                "Partition %s tronquee par le serveur (%d/%d zones) — "
                "donnees incompletes pour cette partition",
                part, res.returned, res.matched,
            )
            incomplete.append(part)
        _collect(res.features)
        time.sleep(0.2)

    total_batches = (len(partitions) + batch_size - 1) // batch_size
    for i in range(0, len(partitions), batch_size):
        batch = partitions[i: i + batch_size]
        quoted = ", ".join(f"'{p}'" for p in batch)
        num = i // batch_size + 1
        print(f"  zone_urba lot {num}/{total_batches} ({len(batch)} partitions)...")
        try:
            res = _wfs_get("wfs_du:zone_urba", f"partition IN ({quoted})", count=MAX_COUNT)
        except Exception as e:
            logger.warning("Lot %d echoue (%s) — reprise partition par partition", num, e)
            for part in batch:
                _fetch_one(part)
            continue

        if res.truncated:
            # Le serveur a coupé : on redécoupe partition par partition.
            logger.info(
                "Lot %d tronque (%d/%d) — redecoupage par partition",
                num, res.returned, res.matched,
            )
            for part in batch:
                _fetch_one(part)
        else:
            _collect(res.features)
        time.sleep(0.2)

    print(f"  -> {len(all_features)} zones PLU/PLUi")
    if incomplete:
        print(f"  ATTENTION: {len(incomplete)} partition(s) incompletes: "
              f"{', '.join(incomplete[:5])}{' ...' if len(incomplete) > 5 else ''}")
    return _to_gdf(all_features)


def fetch_doc_urba_for_partitions(partitions: list[str]) -> gpd.GeoDataFrame:
    """Récupère les métadonnées doc_urba pour les partitions données (batches de 50)."""
    if not partitions:
        return gpd.GeoDataFrame()

    batch_size = 50   # IN() avec ~50 valeurs fonctionne sans startIndex
    all_gdfs: list[gpd.GeoDataFrame] = []

    for i in range(0, len(partitions), batch_size):
        batch = partitions[i: i + batch_size]
        quoted = ", ".join(f"'{p}'" for p in batch)
        cql = f"partition IN ({quoted})"
        batch_num = i // batch_size + 1
        total_batches = (len(partitions) + batch_size - 1) // batch_size
        print(f"  doc_urba batch {batch_num}/{total_batches} ({len(batch)} partitions)...")
        try:
            res = _wfs_get("wfs_du:doc_urba", cql, count=len(batch) + 10)
            if res.truncated:
                logger.warning("doc_urba batch %d tronque (%d/%d)",
                               batch_num, res.returned, res.matched)
            if res.features:
                all_gdfs.append(_to_gdf(res.features))
        except Exception as e:
            logger.warning("Batch %d echoue: %s", batch_num, e)
        time.sleep(0.2)

    if not all_gdfs:
        return gpd.GeoDataFrame()
    return gpd.GeoDataFrame(
        pd.concat(all_gdfs, ignore_index=True),
        geometry="geometry",
        crs="EPSG:4326",
    )
