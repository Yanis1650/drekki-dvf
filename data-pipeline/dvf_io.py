"""Lecture et decouverte des fichiers DVF geolocalises."""

from __future__ import annotations

import logging
from pathlib import Path

import polars as pl

logger = logging.getLogger(__name__)

DVF_SCHEMA = {
    "id_mutation": pl.Utf8,
    "date_mutation": pl.Utf8,
    "nature_mutation": pl.Utf8,
    "valeur_fonciere": pl.Float64,
    "code_postal": pl.Utf8,
    "code_commune": pl.Utf8,
    "nom_commune": pl.Utf8,
    "code_departement": pl.Utf8,
    "id_parcelle": pl.Utf8,
    "type_local": pl.Utf8,
    "surface_reelle_bati": pl.Float64,
    "nombre_pieces_principales": pl.Int32,
    "surface_terrain": pl.Float64,
    "longitude": pl.Float64,
    "latitude": pl.Float64,
}

COLUMNS_TO_SELECT = [
    "id_mutation",
    "date_mutation",
    "nature_mutation",
    "valeur_fonciere",
    "code_commune",
    "id_parcelle",
    "type_local",
    "surface_reelle_bati",
    "nombre_pieces_principales",
    "longitude",
    "latitude",
]


def process_single_file(csv_file: Path) -> pl.DataFrame:
    """Lit une ressource DVF avec un schema controle."""
    logger.info("Processing: %s", csv_file.name)
    frame = pl.read_csv(
        csv_file,
        schema_overrides=DVF_SCHEMA,
        ignore_errors=True,
        infer_schema_length=10_000,
    )
    available = [column for column in COLUMNS_TO_SELECT if column in frame.columns]
    frame = frame.select(available)
    if "code_commune" in frame.columns:
        frame = frame.with_columns(pl.col("code_commune").cast(pl.Utf8).str.zfill(5))
    return frame


def discover_input_files(data_dir: Path, input_glob: str | None = None) -> list[Path]:
    """Retourne les fichiers DVF a traiter sans chemin historique impose."""
    if input_glob:
        return sorted(path for path in data_dir.glob(input_glob) if path.is_file())
    return sorted(data_dir.glob("*_dvf/full_*.csv"))
