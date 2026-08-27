"""Step 8: DFI — filiation cadastrale (parcelles mères / filles).

Alimente `dfi_filiations`, la table que lit l'endpoint `/api/v1/filiation/{id}`.

Sans cette étape, l'API répond 503 `data_unavailable` pour toutes les parcelles
du département : c'est volontaire, l'absence de table signifiant « donnée non
chargée » et non « parcelle sans division ».

Source : Documents de Filiation Informatisés (DGFiP), un fichier texte par
département, publié sur data.gouv.fr.
"""

import sys
from pathlib import Path

from .config import DATA_DIR
from .utils import step_banner

# etl_dfi vit à la racine de data-pipeline, pas dans le paquet des étapes.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def find_dfi_dir() -> Path | None:
    """Localise le dossier DFI dans data/.

    Son nom contient des accents et une plage de départements ; on le repère
    par mots-clés plutôt qu'en le codant en dur.
    """
    if not DATA_DIR.exists():
        return None
    for d in DATA_DIR.iterdir():
        if d.is_dir() and "filiation" in d.name.lower() and "dept" in d.name.lower():
            return d
    return None


def step_dfi(conn, dept, dfi_dir=None):
    """Charge la filiation DFI du département dans la base en construction.

    Args:
        conn: connexion DuckDB ouverte sur la base du département. Réutilisée
            telle quelle — DuckDB refuse une seconde connexion au même fichier.
        dept: code département (ex. "35").
        dfi_dir: dossier des fichiers DFI ; auto-détecté dans data/ si omis.
    """
    step_banner(8, "DFI (filiation cadastrale)")

    dfi_dir = Path(dfi_dir) if dfi_dir else find_dfi_dir()
    if dfi_dir is None or not dfi_dir.exists():
        print("  Donnees DFI absentes de data/ — etape sautee")
        print("  L'endpoint /filiation repondra 503 data_unavailable (comportement voulu)")
        return 0

    from etl_dfi import DFIEtlPipeline

    conn.execute("DROP TABLE IF EXISTS dfi_filiations")

    pipeline = DFIEtlPipeline(conn=conn)
    files = _dept_files(dfi_dir, dept)
    if not files:
        print(f"  Aucun fichier DFI pour le dept {dept} dans {dfi_dir.name} — etape sautee")
        return 0

    total = 0
    for f in files:
        print(f"  Chargement {f.name}...")
        total += pipeline.run(f)

    count = conn.execute("SELECT COUNT(*) FROM dfi_filiations").fetchone()[0]
    communes = conn.execute(
        "SELECT COUNT(DISTINCT code_commune) FROM dfi_filiations"
    ).fetchone()[0]
    print(f"  dfi_filiations: {count:,} relations sur {communes} communes")

    return total


def _dept_files(dfi_dir: Path, dept: str) -> list[Path]:
    """Fichiers DFI du département.

    Les archives nomment le departement tantot `dep035`, tantot `dep35`, tantot
    `dep350` ; chaque `.txt` est en realite un dossier contenant le fichier.
    """
    dept_clean = dept.strip().upper().replace("2A", "2A0").replace("2B", "2B0")
    patterns = {
        f"dep{dept_clean.zfill(3)}",
        f"dep{dept_clean.lstrip('0') or '0'}",
    }
    if len(dept_clean) == 2:
        patterns.add(f"dep{dept_clean}0")

    found = sorted(dfi_dir.glob("dfiano-dep*/dfiano-dep*.txt"))
    if not found:
        found = sorted(dfi_dir.glob("dfiano-dep*.txt"))
    return [f for f in found if any(p in f.as_posix() for p in patterns)]
