"""Téléchargement des PLU/PLUi d'un département depuis le WFS public GPU.

WFS public : https://data.geopf.fr/wfs/ows
Layers GPU :
  - wfs_du:doc_urba_com → lien commune ↔ document (insee, partition)
  - wfs_du:doc_urba     → documents d'urbanisme (partition, idurba, etat, datappro)
  - wfs_du:zone_urba    → zones PLU (partition, insee, typezone, libelle, datappro)

Notes techniques (comportement observé du WFS GPU) :
  - startIndex n'est PAS supporté (retourne HTTP 400)
  - count seul fonctionne ; on découpe par lots de partitions

Le piège de fond — pourquoi le filtre porte sur `partition` et jamais sur
`insee` — est documenté en tête de `plu_wfs/fetch.py`, là où la règle
s'applique. Le lire avant de toucher aux filtres.

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
from pathlib import Path

from plu_wfs import (
    APPROVED,
    WFS_BASE,
    build_doc_urba,
    fetch_commune_partition,
    fetch_doc_urba_for_partitions,
    fetch_zone_urba,
    save_gpkg,
)

logger = logging.getLogger(__name__)


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
