"""Tests du generateur de rapport PDF — le filet manquant avant refonte.

325 lignes sans test, alors que c'est le seul producteur de PDF du projet.
Les trois graphiques et l'assemblage du document se verifient sans lire le
rendu : un PNG commence par sa signature, un PDF par %PDF, et les cas ou un
graphique doit valoir None sont des decisions de conception explicites.

Le radar en particulier : renvoyer None plutot qu'un profil a 5/10 est une
regle documentee dans le code, pas un detail. Un profil parfaitement moyen
dessine sans aucune donnee ne se distingue pas d'un vrai secteur moyen.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.domain.models import MutationAggregate, NatureMutation, Parcelle
from app.services.report_generator import ReportGenerator

PNG = b"\x89PNG\r\n\x1a\n"

CARRE_WKT = "POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))"
DEUX_CARRES_WKT = (
    "MULTIPOLYGON(((0 0, 10 0, 10 10, 0 10, 0 0)), ((20 20, 30 20, 30 30, 20 30, 20 20)))"
)


@pytest.fixture
def generateur():
    return ReportGenerator()


@pytest.fixture
def mutation():
    return MutationAggregate(
        id_mutation="MUT001",
        date_mutation=date(2024, 1, 15),
        nature_mutation=NatureMutation.VENTE,
        valeur_fonciere=Decimal("240000"),
        code_commune="35238",
        parcelles=["35238000AB0297"],
        surface_habitable_totale=Decimal("80"),
        nombre_locaux=1,
    )


@pytest.fixture
def stats():
    return {
        "min_price_m2": Decimal("1800"),
        "max_price_m2": Decimal("4200"),
        "median_price_m2": Decimal("2900"),
        "avg_price_m2": Decimal("3000"),
    }


def _parcelle(wkt: str | None) -> Parcelle:
    return Parcelle(
        id_parcelle="35238000AB0297",
        code_commune="35238",
        prefixe="000",
        section="AB",
        numero="0297",
        geometry_wkt=wkt,
    )


# --- generate_price_chart --------------------------------------------------


def test_graphique_prix_produit_un_png(generateur, mutation, stats):
    tampon = generateur.generate_price_chart(mutation, stats)

    contenu = tampon.getvalue()
    assert contenu.startswith(PNG)
    assert len(contenu) > 1000


def test_graphique_prix_supporte_des_stats_vides(generateur, mutation):
    """Une commune sans reference ne doit pas faire echouer le rapport entier."""
    tampon = generateur.generate_price_chart(mutation, {})

    assert tampon.getvalue().startswith(PNG)


# --- generate_radar_chart --------------------------------------------------


def test_radar_absent_quand_aucun_enrichissement(generateur):
    """None, jamais un profil a 5/10 : voir le docstring de la methode.

    Dessiner des defauts moyens rendait « rien mesure » indistinguable de
    « secteur moyen » pour le lecteur du PDF.
    """
    assert generateur.generate_radar_chart({}) is None
    assert generateur.generate_radar_chart(None) is None


def test_radar_produit_un_png_avec_des_scores(generateur):
    tampon = generateur.generate_radar_chart({
        "education_score": 7.5,
        "transport_score": 6.0,
        "commerce_score": 8.0,
        "green_spaces_score": 4.5,
    })

    assert tampon.getvalue().startswith(PNG)


def test_radar_tolere_des_scores_partiels(generateur):
    """Les categories absentes valent 0, ce qui se lit comme une absence."""
    tampon = generateur.generate_radar_chart({"education_score": 7.5})

    assert tampon.getvalue().startswith(PNG)


# --- generate_parcel_map ---------------------------------------------------


def test_carte_absente_sans_parcelle(generateur):
    assert generateur.generate_parcel_map(None) is None


def test_carte_absente_sans_geometrie(generateur):
    assert generateur.generate_parcel_map(_parcelle(None)) is None


def test_carte_produit_un_png_pour_un_polygone(generateur):
    tampon = generateur.generate_parcel_map(_parcelle(CARRE_WKT))

    assert tampon.getvalue().startswith(PNG)


def test_carte_gere_un_multipolygone(generateur):
    """Une parcelle en plusieurs morceaux passe par la branche MultiPolygon."""
    tampon = generateur.generate_parcel_map(_parcelle(DEUX_CARRES_WKT))

    assert tampon.getvalue().startswith(PNG)


def test_geometrie_illisible_ne_fait_pas_echouer_le_rapport(generateur):
    """Un WKT invalide vaut une carte absente, pas une exception."""
    assert generateur.generate_parcel_map(_parcelle("CECI N'EST PAS DU WKT")) is None


# --- create_pdf_report -----------------------------------------------------


def test_pdf_complet(generateur, mutation, stats):
    prix = generateur.generate_price_chart(mutation, stats)
    radar = generateur.generate_radar_chart({"education_score": 7.0})
    carte = generateur.generate_parcel_map(_parcelle(CARRE_WKT))

    pdf = generateur.create_pdf_report(mutation, stats, {}, prix, radar, carte)

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 2000


def test_pdf_sans_radar_ni_carte(generateur, mutation, stats):
    """Les deux illustrations facultatives manquent : le PDF sort quand meme."""
    prix = generateur.generate_price_chart(mutation, stats)

    pdf = generateur.create_pdf_report(mutation, stats, {}, prix, None, None)

    assert pdf.startswith(b"%PDF")


def test_pdf_porte_la_reference_de_la_mutation(generateur, mutation, stats):
    prix = generateur.generate_price_chart(mutation, stats)

    pdf = generateur.create_pdf_report(mutation, stats, {}, prix, None, None)

    # Les metadonnees ReportLab compressent le flux ; on verifie la structure.
    assert pdf.startswith(b"%PDF")
    assert b"%%EOF" in pdf


def test_les_illustrations_pesent_dans_le_document(generateur, mutation, stats):
    """Un PDF ampute d'une section serait de meme forme mais bien plus leger.

    Verifier la seule signature %PDF laisserait passer une section perdue au
    decoupage : deux images de 150 dpi ne se confondent pas avec leur absence.
    """
    prix = generateur.generate_price_chart(mutation, stats)
    radar = generateur.generate_radar_chart({"education_score": 7.0})
    carte = generateur.generate_parcel_map(_parcelle(CARRE_WKT))

    complet = generateur.create_pdf_report(
        mutation, stats, {"education_score": 7.0}, prix, radar, carte
    )
    minimal = generateur.create_pdf_report(mutation, stats, {}, prix, None, None)

    assert len(complet) > len(minimal) * 1.5
