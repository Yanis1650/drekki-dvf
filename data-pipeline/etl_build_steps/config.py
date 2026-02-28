"""ETL build configuration and paths."""
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"
MAIN_DB = DATA_DIR / "foncier.duckdb"
BDNB_PARQUET = DATA_DIR / "bdnb_stats.parquet"
GPU_WFS_URL = "https://data.geopf.fr/wfs/ows"
W_BDNB, W_DVF, W_DENSIF, W_FRAICHEUR = 0.30, 0.25, 0.25, 0.20
GRID_SIZE = 200
