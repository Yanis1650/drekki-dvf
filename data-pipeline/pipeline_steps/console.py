"""Sortie console de l'orchestrateur, et lancement des sous-commandes."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from pipeline_steps.paths import ROOT


def _hline(char: str = "=", width: int = 62) -> str:
    return char * width


def _banner(step: str, title: str) -> None:
    print(f"\n{_hline()}")
    print(f"  {step} : {title}")
    print(_hline())


def _run(cmd: list[str], cwd: Path = ROOT, critical: bool = True) -> int:
    """Lance une commande et retourne le code de retour."""
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    t0 = time.time()
    result = subprocess.run(cmd, cwd=str(cwd))
    elapsed = time.time() - t0
    status = "OK" if result.returncode == 0 else f"ERREUR (code {result.returncode})"
    print(f"  [{status}] {elapsed:.0f}s")
    if result.returncode != 0 and critical:
        print("\nETAPE BLOQUANTE ECHOUEE — arrêt du pipeline.", file=sys.stderr)
        sys.exit(result.returncode)
    return result.returncode
