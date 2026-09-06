"""Tests de l'orchestrateur departemental.

`run_pipeline.py` delegue l'essentiel a des sous-processus : il n'y a pas
grand-chose a tester de bout en bout sans lancer un ETL complet. Deux choses
meritent pourtant un filet, et ce sont justement celles que le decoupage en
paquet pouvait casser sans bruit.

D'abord `ROOT`, calcule depuis `__file__` : descendre le module d'un dossier
change la profondeur, et tous les chemins pointent alors a cote sans lever la
moindre erreur. Ensuite `_run`, qui decide si une etape en echec arrete le
pipeline ou le laisse continuer — c'est le garde-fou du script entier.

`identite_plui` s'y ajoute : la convention de nommage des archives PLUi
determine la partition sous laquelle le document est enregistre, et une erreur
la rendrait introuvable en base.
"""

import sys
from pathlib import Path

import pytest
from pipeline_steps.console import _run
from pipeline_steps.paths import DATA_DIR, MIGRATIONS_DIR, ROOT
from pipeline_steps.plui import identite_plui


# --- ROOT ------------------------------------------------------------------


def test_root_designe_la_racine_du_depot():
    """Verrou sur la profondeur de `__file__.parent...`.

    Le module vit dans data-pipeline/pipeline_steps/, soit trois crans sous la
    racine. Le deplacer sans corriger le compte ferait pointer ROOT sur
    data-pipeline/, et DATA_DIR sur data-pipeline/data/ — qui n'existe pas.
    """
    assert (ROOT / "pyproject.toml").is_file()
    assert (ROOT / "data-pipeline").is_dir()
    assert DATA_DIR == ROOT / "data"
    assert MIGRATIONS_DIR == ROOT / "migrations"


# --- _run ------------------------------------------------------------------


def test_run_rend_le_code_de_retour_quand_l_etape_n_est_pas_bloquante():
    code = _run([sys.executable, "-c", "raise SystemExit(3)"], critical=False)
    assert code == 3


def test_run_rend_zero_quand_la_commande_reussit():
    assert _run([sys.executable, "-c", "pass"], critical=False) == 0


def test_run_arrete_le_pipeline_sur_une_etape_bloquante():
    """Une etape critique en echec doit stopper net, pas se poursuivre."""
    with pytest.raises(SystemExit) as sortie:
        _run([sys.executable, "-c", "raise SystemExit(4)"], critical=True)

    assert sortie.value.code == 4


def test_run_ne_leve_pas_quand_une_etape_bloquante_reussit():
    assert _run([sys.executable, "-c", "pass"], critical=True) == 0


# --- identite_plui ---------------------------------------------------------


def test_archive_nommee_selon_la_convention():
    partition, datappro, siren = identite_plui(
        Path("243500139_PLUi_20251218.zip"), "35"
    )

    assert siren == "243500139"
    assert datappro == "20251218"
    assert partition == "DU_243500139"


def test_sans_siren_la_partition_retombe_sur_le_departement():
    partition, datappro, siren = identite_plui(Path("PLUi_rennes_20251218.zip"), "35")

    assert siren is None
    assert partition == "DU_PLUI_35"
    assert datappro == "20251218"


@pytest.mark.parametrize("nom", ["243500139_PLUi.zip", "243500139_PLUi_2025.zip"])
def test_date_absente_ou_mal_formee_donne_des_zeros(nom):
    _, datappro, _ = identite_plui(Path(nom), "35")
    assert datappro == "00000000"


def test_siren_de_longueur_incorrecte_ignore():
    """Neuf chiffres exactement : 24350013 n'est pas un SIREN."""
    partition, _, siren = identite_plui(Path("24350013_PLUi_20251218.zip"), "35")

    assert siren is None
    assert partition == "DU_PLUI_35"


def test_partition_stable_quel_que_soit_le_dossier():
    """Seul le nom de l'archive compte, pas son emplacement."""
    a = identite_plui(Path("243500139_PLUi_20251218.zip"), "35")
    b = identite_plui(Path("/tmp/archives/243500139_PLUi_20251218.zip"), "35")

    assert a == b
