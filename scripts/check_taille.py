#!/usr/bin/env python3
"""Verificateur de la limite de 200 lignes par fichier.

La regle est annoncee trois fois — CONTRIBUTING.md, ARCHITECTURE.md deux fois —
et n'etait verifiee nulle part. Trente-deux fichiers la depassaient, jusqu'a
467 lignes. Une regle que rien n'applique n'est pas une regle : c'est une
intention, et elle avait fondu.

    python scripts/check_taille.py          # verifie
    python scripts/check_taille.py --maj    # abaisse les plafonds acquis

Deux regimes.

  - Tout fichier absent du registre est tenu a 200 lignes. C'est le regime
    normal : un fichier neuf ne naitra plus trop gros.

  - Les fichiers deja au-dessus portent un plafond nominatif, egal a leur taille
    au jour ou la regle a ete outillee. Ce plafond ne peut que descendre :
    `--maj` le rabaisse quand un fichier a maigri, jamais l'inverse. Un depart
    a zero aurait demande de refondre trente-deux fichiers d'un coup, ce qui
    aurait fait plus de degats que la dette elle-meme.

Le registre est donc une dette, pas une dispense. Il n'a de sens que s'il se
vide.

Reference : docs/ARCHITECTURE.md, docs/adr/0007-limite-de-taille-des-fichiers.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIMITE = 200
REGISTRE = Path(__file__).with_name("taille_registre.json")

# Arborescences soumises a la regle, avec les extensions concernees.
PERIMETRE = {
    "app": (".py",),
    "data-pipeline": (".py",),
    "frontend/src": (".vue", ".js"),
}

# Exemptions permanentes, avec leur raison. A distinguer du registre : celles-ci
# ne sont pas une dette, elles ne se resorberont pas.
EXEMPT = {
    "frontend/src/styles/tokens.css": "table de jetons : une valeur par ligne, la decouper la rendrait illisible",
}


def fichiers() -> list[Path]:
    trouves: list[Path] = []
    for dossier, extensions in PERIMETRE.items():
        base = ROOT / dossier
        if not base.is_dir():
            continue
        for chemin in sorted(base.rglob("*")):
            if not chemin.is_file() or chemin.suffix not in extensions:
                continue
            if "__pycache__" in chemin.parts or "node_modules" in chemin.parts:
                continue
            trouves.append(chemin)
    return trouves


def lignes(chemin: Path) -> int:
    return len(chemin.read_text(encoding="utf-8", errors="replace").splitlines())


def relatif(chemin: Path) -> str:
    return chemin.relative_to(ROOT).as_posix()


def charger_registre() -> dict[str, int]:
    if not REGISTRE.is_file():
        return {}
    return json.loads(REGISTRE.read_text(encoding="utf-8"))["plafonds"]


def ecrire_registre(plafonds: dict[str, int]) -> None:
    contenu = {
        "_commentaire": (
            "Dette de taille, pas dispense. Chaque entree est le plafond acquis d'un "
            "fichier deja au-dessus de 200 lignes quand la regle a ete outillee. "
            "Ces plafonds ne peuvent que descendre : `python scripts/check_taille.py --maj`. "
            "Une entree disparait quand le fichier repasse sous 200 lignes."
        ),
        "limite": LIMITE,
        "plafonds": dict(sorted(plafonds.items())),
    }
    REGISTRE.write_text(json.dumps(contenu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    maj = "--maj" in sys.argv
    plafonds = charger_registre()
    mesures = {relatif(c): lignes(c) for c in fichiers()}

    if maj:
        nouveaux: dict[str, int] = {}
        abaisses, resorbes = [], []
        for nom, plafond in plafonds.items():
            taille = mesures.get(nom)
            if taille is None:
                resorbes.append(f"{nom} (supprime)")
                continue
            if taille <= LIMITE:
                resorbes.append(f"{nom} ({taille} lignes)")
                continue
            nouveaux[nom] = min(plafond, taille)
            if nouveaux[nom] < plafond:
                abaisses.append(f"{nom} : {plafond} -> {nouveaux[nom]}")
        ecrire_registre(nouveaux)
        for ligne in abaisses:
            print(f"  abaisse   {ligne}")
        for ligne in resorbes:
            print(f"  resorbe   {ligne}")
        restant = sum(v - LIMITE for v in nouveaux.values())
        print(f"\n{len(nouveaux)} fichier(s) encore en dette, {restant} ligne(s) au-dessus de la limite.")
        return 0

    ecarts = []
    for nom, taille in sorted(mesures.items()):
        if nom in EXEMPT or taille <= LIMITE:
            continue
        plafond = plafonds.get(nom)
        if plafond is None:
            ecarts.append((nom, taille, LIMITE, "fichier neuf ou non inscrit"))
        elif taille > plafond:
            ecarts.append((nom, taille, plafond, "plafond acquis depasse"))

    if not ecarts:
        dette = {n: v for n, v in plafonds.items() if n in mesures}
        restant = sum(v - LIMITE for v in dette.values())
        print(f"Taille des fichiers respectee — limite {LIMITE} lignes.")
        if dette:
            print(f"Dette residuelle : {len(dette)} fichier(s), {restant} ligne(s) a resorber.")
        return 0

    print(f"\n{len(ecarts)} fichier(s) au-dela de leur limite.\n", file=sys.stderr)
    for nom, taille, limite, motif in ecarts:
        print(f"  {nom}", file=sys.stderr)
        print(f"    {taille} lignes, limite {limite} — {motif}", file=sys.stderr)
    print(
        "\nUn fichier inscrit au registre ne peut que maigrir. Apres refonte :"
        "\n  python scripts/check_taille.py --maj"
        "\nReference : docs/ARCHITECTURE.md\n",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
