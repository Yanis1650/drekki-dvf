"""Téléchargement des PLU/PLUi d'un département depuis le WFS public GPU.

WFS public : https://data.geopf.fr/wfs/ows
Layers GPU :
  - wfs_du:doc_urba_com → lien commune ↔ document (insee, partition)
  - wfs_du:doc_urba     → documents d'urbanisme (partition, idurba, etat, datappro)
  - wfs_du:zone_urba    → zones PLU (partition, insee, typezone, libelle, datappro)

Notes techniques (comportement observé du WFS GPU) :
  - startIndex n'est PAS supporté (retourne HTTP 400)
  - count seul fonctionne ; on découpe par lots de partitions

**Ne jamais filtrer zone_urba sur `insee`.** Ce champ est très majoritairement
vide dans la couche : sur le département 35, `insee LIKE '35%'` renvoie 1 018
zones là où le filtre par partition en renvoie 22 235 — soit 95 % des zones
perdues en silence. C'est ce qui avait fait conclure à tort que le PLUi de
Rennes Métropole n'était pas publié sur le WFS : ses 4 069 zones y sont, sous
la partition `DU_243500139`, mais sans `insee` renseigné.

Stratégie :
  1. Télécharge doc_urba_com filtré sur insee LIKE '<dept>%'
     → mapping commune ↔ partition faisant autorité, PLUi EPCI compris
       (les documents intercommunaux ont une partition DU_<SIREN>,
        jamais DU_<INSEE> : les chercher par code département les rate)
  2. Télécharge zone_urba filtré sur ces partitions (par lots)
  3. Télécharge doc_urba pour les métadonnées (etat, typedoc)
  4. Construit un GeoPackage avec layers 'doc_urba' et 'zone_urba'
     compatibles avec import_plu.py (une ligne par commune dans doc_urba)

Usage :
    python data-pipeline/download_plu_wfs.py 35
    python data-pipeline/download_plu_wfs.py 35 --out data/plu_35.gpkg
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import time
from pathlib import Path
from typing import NamedTuple

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import shape

logger = logging.getLogger(__name__)

WFS_BASE    = "https://data.geopf.fr/wfs/ows"
MAX_COUNT   = 9999     # compte maximum par requête (startIndex non supporté)
TIMEOUT_S   = 90
RETRY_COUNT = 3
APPROVED    = {"Approuvé", "Opposable", "Applicable", "En vigueur"}

# Codes numériques GPU → libellés attendus par import_plu.py
_ETAT_MAP: dict[str, str] = {
    "01": "En cours d'elaboration",
    "02": "En cours de revision",
    "03": "Opposable",
    "04": "Caduc",
    "05": "Annule",
    "06": "En cours d'instruction",
    "07": "Applicable",
    "08": "En vigueur",
}


# ── Requête WFS simple (sans pagination) ─────────────────────────────────────

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


# ── Mapping commune ↔ partition (doc_urba_com) ───────────────────────────────

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


# ── Téléchargement zone_urba par partitions ──────────────────────────────────

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


# ── Téléchargement doc_urba ───────────────────────────────────────────────────

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


# ── Conversion features → GeoDataFrame ───────────────────────────────────────

def _to_gdf(features: list[dict], crs: str = "EPSG:4326") -> gpd.GeoDataFrame:
    if not features:
        return gpd.GeoDataFrame()
    rows = []
    for f in features:
        props = dict(f.get("properties") or {})
        geom_raw = f.get("geometry")
        props["geometry"] = shape(geom_raw) if geom_raw else None
        rows.append(props)
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=crs)


# ── Construction doc_urba compatible import_plu.py ───────────────────────────

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
                lambda v: _ETAT_MAP.get(str(v), str(v)) if pd.notna(v) else None
            )
        result = zone_part.merge(doc_meta, on="partition", how="left")
    else:
        result = zone_part

    return gpd.GeoDataFrame(
        result,
        geometry="geometry" if "geometry" in result.columns else None,
    )


# ── Sauvegarde GeoPackage ────────────────────────────────────────────────────

def save_gpkg(gdf_doc: gpd.GeoDataFrame, gdf_zones: gpd.GeoDataFrame, out: Path) -> None:
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


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(
        description="Telecharge les PLU/PLUi d'un departement depuis le WFS GPU"
    )
    parser.add_argument("dept", help="Code departement (ex: 35, 29, 2A)")
    parser.add_argument(
        "--out", type=Path, default=None,
        help="Chemin GeoPackage de sortie (defaut: data/plu_<dept>.gpkg)",
    )
    parser.add_argument(
        "--no-plui-copy", dest="plui_copy", action="store_false", default=True,
        help="Ne pas creer data/plui_<dept>.gpkg",
    )
    args = parser.parse_args()
    dept = args.dept
    out = args.out or Path(f"data/plu_{dept}.gpkg")

    print(f"\n=== Telechargement PLU/PLUi dept {dept} depuis WFS GPU ===")
    print(f"  Source : {WFS_BASE}")
    print(f"  Sortie : {out}\n")

    # 1. mapping commune ↔ partition (source de verite, PLUi compris)
    print("[1/5] Telechargement doc_urba_com (mapping commune <-> document)...")
    df_cp = fetch_commune_partition(dept)
    if df_cp.empty:
        print(f"ERREUR: aucun document d'urbanisme pour le departement {dept}.", file=sys.stderr)
        sys.exit(1)

    partitions = sorted(df_cp["partition"].dropna().unique().tolist())
    n_plui = sum(1 for p in partitions if not p.startswith(f"DU_{dept}"))
    print(f"  -> {len(df_cp)} liens, {df_cp['code_commune'].nunique()} communes, "
          f"{len(partitions)} partitions (dont {n_plui} intercommunales)")

    # 2. zones PLU, filtrees sur ces partitions
    print("\n[2/5] Telechargement zone_urba (par partition)...")
    gdf_zones = fetch_zone_urba(partitions)
    if gdf_zones.empty:
        print(f"ERREUR: aucune zone trouvee pour le departement {dept}.", file=sys.stderr)
        sys.exit(1)

    # 3. métadonnées doc_urba
    print("\n[3/5] Telechargement doc_urba (metadonnees)...")
    gdf_doc_raw = fetch_doc_urba_for_partitions(partitions)
    print(f"  -> {len(gdf_doc_raw):,} metadonnees")

    # 4. construction doc_urba compatible
    print("\n[4/5] Construction table doc_urba...")
    gdf_doc = build_doc_urba(df_cp, gdf_doc_raw)

    if "etat" in gdf_doc.columns:
        before = len(gdf_doc)
        gdf_doc = gdf_doc[gdf_doc["etat"].isin(APPROVED) | gdf_doc["etat"].isna()]
        print(f"  Etat approuve : {len(gdf_doc)}/{before} communes conservees")

    # On ne garde que les communes dont le document a effectivement des zones :
    # sans zone, la commune retomberait de toute facon sur le fallback RNU.
    zoned = set(gdf_zones["partition"].dropna().unique())
    before = len(gdf_doc)
    gdf_doc = gdf_doc[gdf_doc["partition"].isin(zoned)]
    if len(gdf_doc) < before:
        print(f"  Zones publiees : {len(gdf_doc)}/{before} communes conservees")

    # 5. sauvegarde
    print(f"\n[5/5] Sauvegarde -> {out}")
    save_gpkg(gdf_doc, gdf_zones, out)

    if args.plui_copy:
        plui_out = out.parent / f"plui_{dept}.gpkg"
        shutil.copy2(out, plui_out)
        print(f"  Copie plui   : {plui_out.name}")

    print("\nTermine! Lancer ensuite :")
    print(f"  python data-pipeline/import_plu.py {dept} --db data/dept{dept}.duckdb --gpkg {out}")


if __name__ == "__main__":
    main()
