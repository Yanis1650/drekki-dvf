"""Integration d'un ZIP PLUi CNIG dans le GeoPackage departemental.

`identite_plui` est isolee et pure : la convention de nommage des archives
(<siren>_PLUi_<datappro>.zip) determine la partition sous laquelle le
document est enregistre, et une erreur la rendrait introuvable.
"""

from __future__ import annotations

from pathlib import Path


def identite_plui(zip_path: Path, dept: str) -> tuple[str, str, str | None]:
    """Deduit (partition, datappro, siren) du nom de l'archive.

    Le SIREN est un nombre de neuf chiffres en tete ; la date d'approbation
    huit chiffres en queue. A defaut, la partition retombe sur le
    departement et la date sur des zeros.
    """
    parts = zip_path.stem.split("_")
    siren = parts[0] if parts[0].isdigit() and len(parts[0]) == 9 else None
    datappro = parts[-1] if len(parts[-1]) == 8 and parts[-1].isdigit() else "00000000"
    partition = f"DU_{siren}" if siren else f"DU_PLUI_{dept}"
    return partition, datappro, siren


def _run_merge_plui(zip_path: Path, gpkg: Path, dept: str) -> None:
    """Intègre un ZIP PLUi CNIG dans le GeoPackage existant."""
    import shutil
    import tempfile
    import zipfile

    import geopandas as gpd
    import pandas as pd

    # Ex : 243500139_PLUi_20251218.zip -> DU_243500139, 20251218
    stem = zip_path.stem
    partition, datappro, siren = identite_plui(zip_path, dept)

    print(f"  Intégration PLUi {partition} (datappro={datappro})...")
    tmpdir = Path(tempfile.mkdtemp())
    try:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(tmpdir)
        shp_candidates = list(tmpdir.rglob("*zone_urba*.shp"))
        if not shp_candidates:
            print("  WARN: aucun *zone_urba*.shp dans le ZIP — skip")
            return

        gdf_new = gpd.read_file(shp_candidates[0])
        gdf_new.columns = [c.lower() for c in gdf_new.columns]
        gdf_new["partition"] = partition
        if "idurba" not in gdf_new.columns:
            gdf_new["idurba"] = stem
        if "datappro" not in gdf_new.columns:
            gdf_new["datappro"] = datappro

        if gdf_new.crs and gdf_new.crs.to_epsg() != 2154:
            gdf_new = gdf_new.to_crs("EPSG:2154")

        # Charger zones existantes et fusionner
        gdf_existing = gpd.read_file(gpkg, layer="zone_urba")
        gdf_existing = gdf_existing[gdf_existing["partition"] != partition]
        common = (set(gdf_existing.columns) & set(gdf_new.columns)) | {"geometry"}
        gdf_merged = gpd.GeoDataFrame(
            pd.concat([
                gdf_existing[[c for c in gdf_existing.columns if c in common]],
                gdf_new[[c for c in gdf_new.columns if c in common]],
            ], ignore_index=True),
            geometry="geometry", crs="EPSG:2154",
        )
        gdf_merged.to_file(gpkg, layer="zone_urba", driver="GPKG")
        print(f"  zone_urba : {len(gdf_merged):,} zones après fusion")

        # Récupérer les communes du PLUi via WFS GPU doc_urba_com
        _add_plui_communes(gpkg, partition, datappro, siren)

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    shutil.copy2(gpkg, gpkg.parent / f"plui_{dept}.gpkg")


def _add_plui_communes(gpkg: Path, partition: str, datappro: str, siren: str | None) -> None:
    import geopandas as gpd
    import pandas as pd
    import requests

    wfs_url = "https://data.geopf.fr/wfs/ows"
    commune_list: list[str] = []
    if siren:
        try:
            r = requests.get(wfs_url, params={
                "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
                "TYPENAMES": "wfs_du:doc_urba_com", "outputFormat": "application/json",
                "count": 300, "CQL_FILTER": f"partition = '{partition}'",
            }, timeout=30)
            if r.status_code == 200:
                commune_list = [
                    str(f["properties"].get("insee") or f["properties"].get("commune", ""))
                    for f in r.json().get("features", [])
                    if f.get("properties")
                ]
                commune_list = [c for c in commune_list if len(c) in (4, 5)]
        except Exception as e:
            print(f"  WARN: WFS doc_urba_com : {e}")

    gdf_doc = gpd.read_file(gpkg, layer="doc_urba")
    gdf_doc = gdf_doc[gdf_doc["partition"] != partition]
    if commune_list:
        rows = []
        for code in commune_list:
            row = {col: None for col in gdf_doc.columns}
            row.update({"partition": partition, "code_commune": code,
                        "typedoc": "PLUi", "etat": "Opposable",
                        "datappro": datappro})
            if "siren" in row and siren:
                row["siren"] = siren
            rows.append(row)
        gdf_doc = pd.concat(
            [gdf_doc, gpd.GeoDataFrame(rows, geometry="geometry", crs=gdf_doc.crs)],
            ignore_index=True,
        )
        print(f"  doc_urba : {len(commune_list)} communes PLUi ajoutées")
    gdf_doc_final = gpd.GeoDataFrame(gdf_doc, geometry="geometry", crs=gdf_doc.crs)
    gdf_doc_final.to_file(gpkg, layer="doc_urba", driver="GPKG")
