"""Tests du service de rapport parcelle.

Le rendu passe par Playwright dans un sous-processus : on ne le teste pas ici.
Restent deux choses qui cassent en silence.

Les deux filtres de formatage, d'abord : ils sont enregistres dans Jinja sous
les noms `format_currency` et `format_date`, et les gabarits les appellent par
ces noms-la. Une faute de frappe cote enregistrement ne se voit qu'a la
generation du PDF, en production.

Le chemin d'execution ensuite : `_render_html_to_pdf_sync` lance un
sous-processus depuis RACINE_DEPOT. La profondeur depend de l'emplacement du
module ; la changer, ou deplacer le fichier, ferait demarrer le sous-processus
au mauvais endroit, sans erreur lisible.
"""

from decimal import Decimal

import pytest

from app.services.parcel_report_service import ParcelReportService

FORMAT_CURRENCY = ParcelReportService._format_currency
FORMAT_DATE = ParcelReportService._format_date


# --- format_currency -------------------------------------------------------


@pytest.mark.parametrize(
    ("valeur", "attendu"),
    [
        (240000, "240 000 €"),
        (240000.0, "240 000 €"),
        (Decimal("240000"), "240 000 €"),
        (Decimal("1234567"), "1 234 567 €"),
        (0, "0 €"),
        (999, "999 €"),
    ],
)
def test_montant_en_euros_avec_espaces(valeur, attendu):
    """Separateur de milliers francais : une espace, pas une virgule."""
    assert FORMAT_CURRENCY(valeur) == attendu


def test_montant_absent_donne_na():
    assert FORMAT_CURRENCY(None) == "N/A"


def test_montant_arrondi_a_l_euro():
    assert FORMAT_CURRENCY(Decimal("1234.67")) == "1 235 €"


# --- format_date -----------------------------------------------------------


@pytest.mark.parametrize(
    ("valeur", "attendu"),
    [
        ("2024-01-15", "15/01/2024"),
        ("2024-01-15T10:30:00", "15/01/2024"),
        ("2024-12-31", "31/12/2024"),
    ],
)
def test_date_au_format_francais(valeur, attendu):
    assert FORMAT_DATE(valeur) == attendu


@pytest.mark.parametrize("valeur", [None, "", 0])
def test_date_absente_donne_na(valeur):
    assert FORMAT_DATE(valeur) == "N/A"


def test_date_illisible_rendue_telle_quelle():
    """Mieux vaut afficher la valeur brute qu'echouer sur tout le rapport."""
    assert FORMAT_DATE("pas une date") == "pas une date"


# --- enregistrement des filtres Jinja --------------------------------------


class _DepotFactice:
    """Le service n'appelle pas le depot a la construction."""


@pytest.fixture
def service(tmp_path):
    gabarits = tmp_path / "templates"
    gabarits.mkdir()
    return ParcelReportService(
        land_repository=_DepotFactice(),
        duckdb_path=tmp_path / "foncier.duckdb",
        template_dir=gabarits,
    )


def test_les_filtres_sont_enregistres_sous_les_noms_attendus(service):
    """Les gabarits ecrivent `| format_currency` et `| format_date`."""
    filtres = service._jinja_env.filters

    assert filtres["format_currency"] is ParcelReportService._format_currency
    assert filtres["format_date"] is ParcelReportService._format_date


def test_les_filtres_fonctionnent_dans_un_gabarit(service):
    rendu = service._jinja_env.from_string(
        "{{ v | format_currency }} le {{ d | format_date }}"
    ).render(v=Decimal("240000"), d="2024-01-15")

    assert rendu == "240 000 € le 15/01/2024"


def test_l_autoescape_est_actif(service):
    """Les donnees viennent de la base : elles ne doivent pas injecter de HTML."""
    rendu = service._jinja_env.from_string("{{ v }}").render(v="<script>x</script>")

    assert "<script>" not in rendu


# --- chemin d'execution du sous-processus ----------------------------------


def test_le_module_sait_retrouver_la_racine_du_depot():
    """Verrou sur RACINE_DEPOT, d'ou part le sous-processus Playwright.

    Le module vit dans app/services/, soit deux crans sous la racine. L'y
    deplacer sans corriger le compte ferait demarrer le sous-processus
    Playwright dans app/, ou `python -m app.scripts.html_to_pdf` est
    introuvable.
    """
    from app.services.parcel_report_service import RACINE_DEPOT

    assert (RACINE_DEPOT / "pyproject.toml").is_file()
    assert (RACINE_DEPOT / "app" / "scripts" / "html_to_pdf.py").is_file()
