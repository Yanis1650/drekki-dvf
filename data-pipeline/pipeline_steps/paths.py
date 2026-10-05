"""Chemins de reference du depot.

ROOT se calcule depuis `__file__`, donc la profondeur depend de l'endroit ou ce
fichier se trouve : `data-pipeline/pipeline_steps/paths.py` est a trois crans
de la racine. Deplacer ce module d'un dossier casse tous les chemins en
silence — c'est pourquoi `tests/test_run_pipeline.py` verifie que ROOT designe
bien la racine du depot.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data"
MIGRATIONS_DIR = ROOT / "migrations"
