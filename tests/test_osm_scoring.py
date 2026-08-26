"""Tests scoring OSM enrichment — 5 cas :
  1. Gare à 600m → transit_score ≈ 10.0 (pic gaussien), nuisances_score non impacté
  2. Gare à 50m  → transit_score < 5.0 (trop proche, cloche en dessous du seuil)
  3. Voie ferrée traversante → nuisances_score impacté, transit_score non impacté
  4. Aéroport à 2km → nuisances_score pénalisé
  5. Score global vérifié avec les 6 pondérations (somme=1.00)
"""

import sys
import types
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

# Mocker les librairies lourdes non installées dans l'env de test.
# On utilise MagicMock() qui gère dynamiquement tout attribut (pl.LazyFrame, etc.)
# mais on lui ajoute __path__ pour qu'il soit reconnu comme package par Python.
def _mock_pkg(name: str) -> MagicMock:
    m = MagicMock()
    m.__path__ = []
    m.__package__ = name
    m.__name__ = name
    return m

for _pkg in ("polars", "geopandas", "osmnx", "fiona", "pyogrio",
             "shapely", "owslib", "pyproj", "requests", "aiohttp"):
    if _pkg not in sys.modules:
        sys.modules[_pkg] = _mock_pkg(_pkg)

for _sub in (
    "polars.exceptions", "polars.selectors",
    "shapely.geometry", "shapely.validation", "shapely.ops",
    "owslib.wfs", "owslib.util",
    "pyproj.transformer",
):
    if _sub not in sys.modules:
        sys.modules[_sub] = MagicMock()

# Imports applicatifs — après le mock
from app.services.enrichment.proximity_scorer import ProximityResult  # noqa: E402
from app.services.enrichment.quality_scorer import DecayFunction, QualityScorer  # noqa: E402
from app.domain.models import EnrichmentScore  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_proximity(
    category: str,
    nearest_m: float | None,
    count_500m: int = 0,
    count_1km: int = 0,
    poi_types: list[str] | None = None,
) -> ProximityResult:
    return ProximityResult(
        category=category,
        nearest_distance_m=nearest_m,
        count_500m=count_500m,
        count_1km=count_1km,
        count_2km=0,
        poi_types=poi_types or [],
    )


def _no_poi(category: str) -> ProximityResult:
    """Aucun POI trouvé pour cette catégorie."""
    return ProximityResult(
        category=category,
        nearest_distance_m=None,
        count_500m=0,
        count_1km=0,
        count_2km=0,
        poi_types=[],
    )


# ---------------------------------------------------------------------------
# Classe 1 : Fonction gaussienne (tests unitaires DecayFunction)
# ---------------------------------------------------------------------------

class TestGaussianDecay:
    """Tests directs sur la formule cloche."""

    def test_pic_a_600m(self):
        """À 600m (pic), la gaussienne retourne ≈ 10.0."""
        score = DecayFunction.gaussian(600, peak_distance=600, sigma=300)
        assert abs(score - 10.0) < 0.01, f"Attendu ≈10.0, obtenu {score}"

    def test_demi_largeur_a_300m(self):
        """À 300m (= pic − σ), score ≈ 6.07 (exp(-0.5)*10)."""
        score = DecayFunction.gaussian(300, peak_distance=600, sigma=300)
        assert abs(score - 6.07) < 0.05, f"Attendu ≈6.07, obtenu {score}"

    def test_demi_largeur_a_900m(self):
        """À 900m (= pic + σ), score ≈ 6.07 — symétrie de la cloche."""
        score = DecayFunction.gaussian(900, peak_distance=600, sigma=300)
        assert abs(score - 6.07) < 0.05, f"Attendu ≈6.07, obtenu {score}"

    def test_a_1200m(self):
        """À 1200m (= pic + 2σ), score ≈ 1.35 (exp(-2)*10)."""
        score = DecayFunction.gaussian(1200, peak_distance=600, sigma=300)
        assert abs(score - 1.35) < 0.05, f"Attendu ≈1.35, obtenu {score}"

    def test_distance_nulle(self):
        """À 0m (gare sous les pieds), score = exp(-2)*10 ≈ 1.35 (pas 10)."""
        score = DecayFunction.gaussian(0, peak_distance=600, sigma=300)
        assert score < 2.0, f"Trop proche doit donner un score < 2, obtenu {score}"

    def test_distance_negative_retourne_zero(self):
        score = DecayFunction.gaussian(-10, peak_distance=600, sigma=300)
        assert score == 0.0


# ---------------------------------------------------------------------------
# Classe 2 : QualityScorer.score_transit
# ---------------------------------------------------------------------------

class TestTransitScoring:
    scorer = QualityScorer()

    def test_gare_a_600m_transit_score_proche_10(self):
        """Gare à 600m → transit_score ≈ 10.0 (pic optimal TOD)."""
        prox = _make_proximity("transit", nearest_m=600.0, poi_types=["station"])
        result = self.scorer.score_transit(prox)
        assert float(result.score) >= 9.5, (
            f"Gare à 600m attendu ≥9.5, obtenu {result.score}"
        )

    def test_gare_a_50m_transit_score_faible(self):
        """Gare à 50m → transit_score < 5.0 (bruit, effet cloche en dessous du pic)."""
        prox = _make_proximity("transit", nearest_m=50.0, poi_types=["station"])
        result = self.scorer.score_transit(prox)
        assert float(result.score) < 5.0, (
            f"Gare à 50m trop proche — attendu <5.0, obtenu {result.score}"
        )

    def test_pas_de_gare_transit_score_nul(self):
        """Sans gare dans la zone, transit_score = 0.0."""
        prox = _no_poi("transit")
        result = self.scorer.score_transit(prox)
        assert float(result.score) == 0.0, (
            f"Sans gare, transit_score doit être 0.0, obtenu {result.score}"
        )

    def test_categorie_retournee(self):
        prox = _make_proximity("transit", nearest_m=600.0)
        result = self.scorer.score_transit(prox)
        assert result.category == "transit"

    def test_details_contiennent_raw_gaussian(self):
        prox = _make_proximity("transit", nearest_m=600.0)
        result = self.scorer.score_transit(prox)
        assert "raw_gaussian" in result.details
        assert abs(result.details["raw_gaussian"] - 10.0) < 0.1


# ---------------------------------------------------------------------------
# Classe 3 : Séparation transit / nuisances
# ---------------------------------------------------------------------------

class TestTransitVsNuisances:
    scorer = QualityScorer()

    def test_voie_ferree_impacte_nuisances_pas_transit(self):
        """Voie ferrée à 200m → nuisances_score pénalisé, transit_score non affecté.

        Le nuisances_scorer utilise la catégorie 'nuisances' (type_poi='nuisance')
        qui contient railway=rail mais PAS les gares.
        Le transit_scorer utilise la catégorie 'transit' (type_poi='transit').
        """
        prox_nuisances = _make_proximity(
            "nuisances", nearest_m=200.0, poi_types=["rail"]
        )
        prox_transit = _no_poi("transit")

        nuisances_score = self.scorer.score_nuisances(prox_nuisances)
        transit_score   = self.scorer.score_transit(prox_transit)

        # Voie ferrée proche → nuisances pénalisé (score bas)
        assert float(nuisances_score.score) < 5.0, (
            f"Voie ferrée à 200m doit pénaliser nuisances — obtenu {nuisances_score.score}"
        )
        # Aucune gare dans la zone → transit_score = 0
        assert float(transit_score.score) == 0.0, (
            f"transit_score ne doit pas être impacté par une voie ferrée — obtenu {transit_score.score}"
        )

    def test_gare_impacte_transit_pas_nuisances(self):
        """Gare à 600m → transit_score élevé, nuisances_score non impacté."""
        prox_transit   = _make_proximity("transit", nearest_m=600.0, poi_types=["station"])
        prox_nuisances = _no_poi("nuisances")

        transit_score   = self.scorer.score_transit(prox_transit)
        nuisances_score = self.scorer.score_nuisances(prox_nuisances)

        assert float(transit_score.score) >= 9.5, (
            f"Gare à 600m → transit_score attendu ≥9.5, obtenu {transit_score.score}"
        )
        # Aucune nuisance → score maximum (10 - 0 pénalité = 10)
        assert float(nuisances_score.score) == 10.0, (
            f"Sans nuisance, nuisances_score doit être 10.0, obtenu {nuisances_score.score}"
        )

    def test_aeroport_a_2km_penalise_nuisances(self):
        """Aéroport à 2000m → nuisances_score pénalisé (facteur négatif)."""
        prox = _make_proximity("nuisances", nearest_m=2000.0, poi_types=["aerodrome"])
        result = self.scorer.score_nuisances(prox)
        # À 2km avec half-life=400m : penalty = 10 * exp(-ln2 * 2000/400)
        # = 10 * exp(-3.47) ≈ 0.31 → score ≈ 9.69
        # Mais un aéroport est significativement pénalisant même à distance
        assert float(result.score) < 10.0, (
            f"Aéroport à 2km doit pénaliser (score < 10), obtenu {result.score}"
        )
        assert float(result.score) > 0.0


# ---------------------------------------------------------------------------
# Classe 4 : Score global à 6 pondérations
# ---------------------------------------------------------------------------

class TestGlobalScore:
    """Vérifie que global_score respecte les 6 pondérations (somme = 1.00)."""

    def test_global_score_ponderation_correcte(self):
        """Score global = somme pondérée à 6 composantes."""
        score = EnrichmentScore(
            id_parcelle="35238000AB0001",
            schools_score=Decimal("8.0"),
            transport_score=Decimal("6.0"),
            transit_score=Decimal("9.0"),
            nuisances_score=Decimal("7.0"),
            green_spaces_score=Decimal("5.0"),
            commerce_score=Decimal("4.0"),
        )
        # Calcul attendu :
        # 8.0*0.20 + 6.0*0.15 + 9.0*0.20 + 7.0*0.20 + 5.0*0.10 + 4.0*0.15
        # = 1.60 + 0.90 + 1.80 + 1.40 + 0.50 + 0.60 = 6.80
        expected = Decimal("6.80")
        assert score.global_score == expected, (
            f"Score global attendu {expected}, obtenu {score.global_score}"
        )

    def test_global_score_transit_influence(self):
        """transit_score à 0 réduit le score global d'exactement 20% * 10 = 2.0."""
        avec_transit = EnrichmentScore(
            id_parcelle="35238000AB0001",
            schools_score=Decimal("5.0"),
            transport_score=Decimal("5.0"),
            transit_score=Decimal("10.0"),
            nuisances_score=Decimal("5.0"),
            green_spaces_score=Decimal("5.0"),
            commerce_score=Decimal("5.0"),
        )
        sans_transit = EnrichmentScore(
            id_parcelle="35238000AB0001",
            schools_score=Decimal("5.0"),
            transport_score=Decimal("5.0"),
            transit_score=Decimal("0.0"),
            nuisances_score=Decimal("5.0"),
            green_spaces_score=Decimal("5.0"),
            commerce_score=Decimal("5.0"),
        )
        diff = avec_transit.global_score - sans_transit.global_score
        assert abs(diff - Decimal("2.0")) < Decimal("0.01"), (
            f"La différence attendue est 2.0 (20% × 10), obtenu {diff}"
        )

    def test_global_score_somme_poids_unite(self):
        """Vérification indépendante : si tous les scores = 5, global = 5."""
        score = EnrichmentScore(
            id_parcelle="35238000AB0001",
            schools_score=Decimal("5.0"),
            transport_score=Decimal("5.0"),
            transit_score=Decimal("5.0"),
            nuisances_score=Decimal("5.0"),
            green_spaces_score=Decimal("5.0"),
            commerce_score=Decimal("5.0"),
        )
        assert score.global_score == Decimal("5.00"), (
            f"Tous scores à 5 → global attendu 5.00, obtenu {score.global_score}"
        )
