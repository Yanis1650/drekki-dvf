"""ETL build steps for per-department DuckDB generation."""

from .bdtopo import step_bdtopo
from .confidence import step_confidence
from .config import (
    BDNB_PARQUET,
    DATA_DIR,
    GRID_SIZE,
    GPU_WFS_URL,
    MAIN_DB,
    W_BDNB,
    W_DENSIF,
    W_DVF,
    W_FRAICHEUR,
)
from .densification import step_densification
from .golden_join import step_golden_join
from .gpu import step_gpu
from .optimize import step_optimize
from .rnu import step_rnu

__all__ = [
    "step_golden_join",
    "step_densification",
    "step_gpu",
    "step_bdtopo",
    "step_rnu",
    "step_confidence",
    "step_optimize",
    "DATA_DIR",
    "MAIN_DB",
    "BDNB_PARQUET",
    "GRID_SIZE",
    "GPU_WFS_URL",
    "W_BDNB",
    "W_DVF",
    "W_DENSIF",
    "W_FRAICHEUR",
]
