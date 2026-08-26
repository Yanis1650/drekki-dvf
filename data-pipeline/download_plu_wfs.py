"""Téléchargement des PLU/PLUi d'un département depuis le WFS public GPU.

WFS public : https://data.geopf.fr/wfs/ows
Layers GPU :
  - wfs_du:doc_urba  → documents d'urbanisme (partition, idurba, etat, datappro)
  - wfs_du:zone_urba → zones PLU (partition, insee, typezone, libelle, datappro, the_geom)

Notes techniques (comportement observé du WFS GPU) :
  - startIndex n'est PAS supporté (retourne HTTP 400)
  - count seul fonctionne, le serveur plafonne à ~1000 features/réponse
  - Pour un département moyen (~1000 zones), un seul appel suffit
  - Pour un dept plus grand, on découpe par plages INSEE (35001-35100, etc.)

Stratégie :
  1. Télécharge zone_urba filtré sur insee LIKE '<dept>%' → couvre PLU + PLUi
  2. Extrait les partitions des zones
  3. Télécharge doc_urba pour ces partitions (métadonnées : etat, typedoc)
  4. Construit un GeoPackage avec layers 'doc_urba' et 'zone_urba'
     compatibles avec import_plu.py (champ code_commune dans doc_urba)

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

def _wfs_get(typename: str, cql_filter: str, count: int = MAX_COUNT) -> list[dict]:
    """
    Effectue une requête WFS GetFeature et retourne les features GeoJSON.

    Important : startIndex n'est pas supporté par ce WFS.
    Si count < nombre réel de features, on découpe les requêtes par filtre.
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
            return r.json().get("features", [])
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
    return []


# ── Téléchargement zone_urba avec découpage par plages INSEE ─────────────────

def fetch_zone_urba(dept: str) -> gpd.GeoDataFrame:
    """
    Récupère toutes les zones PLU du département.

    Comme startIndex n'est pas supporté, on découpe par plages de 100 codes INSEE
    pour s'assurer de tout récupérer si le nombre de zones dépasse MAX_COUNT.
    Exemples :
      - dept 35 → 1018 zones → 1 seul appel suffit
      - dept 59 → peut nécessiter plusieurs appels découpés par plage
    """
    print(f"  Strategie : decoupage par plages INSEE pour dept {dept}")

    # Plages INSEE : <dept>001-<dept>100, <dept>101-<dept>200, ...
    # Adapté pour codes communes 3-digits (ex: 35001 → 35 + 001)
    dept_prefix_len = len(dept)
    all_features: list[dict] = []
    seen_gids: set = set()

    # D'abord essayer un seul appel pour tout le dept
    try:
        logger.info("Appel unique zone_urba dept %s...", dept)
        feats = _wfs_get("wfs_du:zone_urba", f"insee LIKE '{dept}%'", count=MAX_COUNT)
        logger.info("Appel unique: %d features", len(feats))

        if feats:
            for f in feats:
                gid = f.get("id") or f.get("properties", {}).get("gid")
                if gid not in seen_gids:
                    seen_gids.add(gid)
                    all_features.append(f)

            # Si on a moins que MAX_COUNT, on a tout
            if len(feats) < MAX_COUNT:
                print(f"  -> {len(all_features)} zones (appel unique)")
                return _to_gdf(all_features)

    except Exception as e:
        logger.warning("Appel unique echoue: %s", e)

    # Si on arrive ici, il faut decouper par plages de 100
    print("  -> Decoupage par plages de 100 codes INSEE...")
    for start in range(1, 1000, 100):
        low = f"{dept}{start:03d}"
        high = f"{dept}{min(start + 99, 999):03d}"
        cql = f"insee >= '{low}' AND insee <= '{high}'"
        try:
            feats = _wfs_get("wfs_du:zone_urba", cql, count=MAX_COUNT)
            for f in feats:
                gid = f.get("id") or f.get("properties", {}).get("gid")
                if gid not in seen_gids:
                    seen_gids.add(gid)
                    all_features.append(f)
            if feats:
                logger.info("  Plage %s-%s: %d features", low, high, len(feats))
        except Exception as e:
            logger.warning("Plage %s-%s: %s", low, high, e)
        time.sleep(0.2)

    print(f"  -> {len(all_features)} zones PLU/PLUi")
    return _to_gdf(all_features)


# ── Téléchargement doc_urba ───────────────────────────────────────────────────

def fetch_doc_urba_for_partitions(partitions: list[str]) -> gpd.GeoDataFrame:
    """Récupère les métadonnées doc_urba pour les partitions données (batches de 50)."""
    if not partitions:
        return gpd.GeoDataFrame()

    BATCH = 50   # IN() avec ~50 valeurs fonctionne sans startIndex
    all_gdfs: list[gpd.GeoDataFrame] = []

    for i in range(0, len(partitions), BATCH):
        batch = partitions[i: i + BATCH]
        quoted = ", ".join(f"'{p}'" for p in batch)
        cql = f"partition IN ({quoted})"
        batch_num = i // BATCH + 1
        total_batches = (len(partitions) + BATCH - 1) // BATCH
        print(f"  doc_urba batch {batch_num}/{total_batches} ({len(batch)} partitions)...")
        try:
            feats = _wfs_get("wfs_du:doc_urba", cql, count=len(batch) + 10)
            if feats:
                all_gdfs.append(_to_gdf(feats))
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

def build_doc_urba(gdf_zones: gpd.GeoDataFrame, gdf_doc_raw: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Construit la table doc_urba avec le champ 'code_commune' requis par import_plu.py.

    import_plu.py cherche un champ 'code_commune', 'insee' ou 'code_insee'
    dans la layer doc_urba du GeoPackage pour filtrer par département.
    """
    if gdf_zones.empty:
        return gpd.GeoDataFrame()

    # Mapping partition → code_commune extrait de zone_urba.insee
    zone_part = (
        gdf_zones[["partition", "insee"]]
        .dropna(subset=["partition", "insee"])
        .drop_duplicates()
        .groupby("partition", as_index=False)
        .first()
        .rename(columns={"insee": "code_commune"})
    )

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

    # 1. zones PLU
    print("[1/4] Telechargement zone_urba...")
    gdf_zones = fetch_zone_urba(dept)
    if gdf_zones.empty:
        print(f"ERREUR: aucune zone trouvee pour le departement {dept}.", file=sys.stderr)
        sys.exit(1)

    partitions = gdf_zones["partition"].dropna().unique().tolist()
    n_plui = sum(1 for p in partitions if not p.startswith(f"DU_{dept}"))
    print(f"  Partitions : {len(partitions)} (dont ~{n_plui} PLUi EPCI)")

    # 2. métadonnées doc_urba
    print("\n[2/4] Telechargement doc_urba (metadonnees)...")
    gdf_doc_raw = fetch_doc_urba_for_partitions(partitions)
    print(f"  -> {len(gdf_doc_raw):,} metadonnees")

    # 3. construction doc_urba compatible
    print("\n[3/4] Construction table doc_urba...")
    gdf_doc = build_doc_urba(gdf_zones, gdf_doc_raw)

    if "etat" in gdf_doc.columns:
        before = len(gdf_doc)
        gdf_doc = gdf_doc[gdf_doc["etat"].isin(APPROVED) | gdf_doc["etat"].isna()]
        print(f"  Etat approuve : {len(gdf_doc)}/{before} partitions conservees")

    # 4. sauvegarde
    print(f"\n[4/4] Sauvegarde -> {out}")
    save_gpkg(gdf_doc, gdf_zones, out)

    if args.plui_copy:
        plui_out = out.parent / f"plui_{dept}.gpkg"
        shutil.copy2(out, plui_out)
        print(f"  Copie plui   : {plui_out.name}")

    print(f"\nTermine! Lancer ensuite :")
    print(f"  python data-pipeline/import_plu.py {dept} --db data/dept{dept}.duckdb --gpkg {out}")


if __name__ == "__main__":
    main()
