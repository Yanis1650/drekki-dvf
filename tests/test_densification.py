"""Tests unitaires pour l'indicateur de Potentiel de Densification (ZAN).

Teste le modèle DensificationScore et les méthodes repository.
"""

from decimal import Decimal

import pytest

from app.domain.models import DensificationScore


class TestDensificationScore:
    """Tests du modèle DensificationScore."""

    def test_creation_score_fort(self):
        """Test création score avec potentiel FORT (≥20%)."""
        score = DensificationScore(
            id_parcelle="35238000AB0297",
            surface_parcelle_m2=Decimal("1000.0"),
            surface_plancher_m2=Decimal("100.0"),
            ces_actuel=Decimal("0.10"),  # 10%
            ces_potentiel=Decimal("0.40"),  # 40%
        )

        assert score.potentiel_densification == Decimal("0.30")  # 30%
        assert score.surface_constructible_restante == Decimal("300.0")  # 300 m²
        assert score.categorie == "FORT"

    def test_creation_score_moyen(self):
        """Test création score avec potentiel MOYEN (10-20%)."""
        score = DensificationScore(
            id_parcelle="35238000AB0298",
            surface_parcelle_m2=Decimal("800.0"),
            surface_plancher_m2=Decimal("240.0"),
            ces_actuel=Decimal("0.30"),  # 30%
            ces_potentiel=Decimal("0.45"),  # 45%
        )

        assert score.potentiel_densification == Decimal("0.15")  # 15%
        assert score.surface_constructible_restante == Decimal("120.0")  # 120 m²
        assert score.categorie == "MOYEN"

    def test_creation_score_faible(self):
        """Test création score avec potentiel FAIBLE (0-10%)."""
        score = DensificationScore(
            id_parcelle="35238000AB0299",
            surface_parcelle_m2=Decimal("500.0"),
            surface_plancher_m2=Decimal("175.0"),
            ces_actuel=Decimal("0.35"),  # 35%
            ces_potentiel=Decimal("0.40"),  # 40%
        )

        assert score.potentiel_densification == Decimal("0.05")  # 5%
        assert score.surface_constructible_restante == Decimal("25.0")  # 25 m²
        assert score.categorie == "FAIBLE"

    def test_creation_score_sature(self):
        """Test création score SATURÉ (0%)."""
        score = DensificationScore(
            id_parcelle="35238000AB0300",
            surface_parcelle_m2=Decimal("600.0"),
            surface_plancher_m2=Decimal("300.0"),
            ces_actuel=Decimal("0.50"),  # 50%
            ces_potentiel=Decimal("0.40"),  # 40%
        )

        # Potentiel négatif devient 0
        assert score.potentiel_densification == Decimal("0.0")
        assert score.surface_constructible_restante == Decimal("0.0")
        assert score.categorie == "SATURE"

    def test_ces_potentiel_default(self):
        """Test valeur par défaut CES potentiel (40%)."""
        score = DensificationScore(
            id_parcelle="35238000AB0301",
            surface_parcelle_m2=Decimal("1000.0"),
            surface_plancher_m2=Decimal("100.0"),
            ces_actuel=Decimal("0.10"),
        )

        assert score.ces_potentiel == Decimal("0.40")

    def test_seuil_fort_exact(self):
        """Test seuil exact FORT (20%)."""
        score = DensificationScore(
            id_parcelle="35238000AB0302",
            surface_parcelle_m2=Decimal("1000.0"),
            surface_plancher_m2=Decimal("200.0"),
            ces_actuel=Decimal("0.20"),  # 20%
            ces_potentiel=Decimal("0.40"),  # 40%
        )

        assert score.potentiel_densification == Decimal("0.20")  # Exactement 20%
        assert score.categorie == "FORT"  # ≥ 20% → FORT

    def test_seuil_moyen_exact(self):
        """Test seuil exact MOYEN (10%)."""
        score = DensificationScore(
            id_parcelle="35238000AB0303",
            surface_parcelle_m2=Decimal("1000.0"),
            surface_plancher_m2=Decimal("300.0"),
            ces_actuel=Decimal("0.30"),  # 30%
            ces_potentiel=Decimal("0.40"),  # 40%
        )

        assert score.potentiel_densification == Decimal("0.10")  # Exactement 10%
        assert score.categorie == "MOYEN"  # ≥ 10% → MOYEN

    def test_ces_actuel_zero(self):
        """Test CES actuel à 0% (parcelle vide)."""
        score = DensificationScore(
            id_parcelle="35238000AB0304",
            surface_parcelle_m2=Decimal("2000.0"),
            surface_plancher_m2=Decimal("0.0"),
            ces_actuel=Decimal("0.0"),
            ces_potentiel=Decimal("0.40"),
        )

        assert score.potentiel_densification == Decimal("0.40")  # 40%
        assert score.surface_constructible_restante == Decimal("800.0")  # 800 m²
        assert score.categorie == "FORT"

    def test_ces_actuel_superieur_potentiel(self):
        """Test CES actuel > CES potentiel (bâtiment multi-étages)."""
        # Note: ces_actuel est cappé à 9.9999 dans l'ETL, mais le modèle accepte jusqu'à 1.0
        # Pour tester la logique, on utilise 0.8 (80%) > 0.4 (40%)
        score = DensificationScore(
            id_parcelle="35238000AB0305",
            surface_parcelle_m2=Decimal("500.0"),
            surface_plancher_m2=Decimal("400.0"),
            ces_actuel=Decimal("0.80"),  # 80% (bâtiment dense)
            ces_potentiel=Decimal("0.40"),  # 40%
        )

        # Potentiel négatif → 0
        assert score.potentiel_densification == Decimal("0.0")
        assert score.surface_constructible_restante == Decimal("0.0")
        assert score.categorie == "SATURE"


@pytest.mark.asyncio
class TestDensificationRepository:
    """Tests des méthodes repository (nécessite DuckDB)."""

    async def test_get_densification_score_existant(self, duckdb_repo):
        """Test récupération score existant."""
        score = await duckdb_repo.get_densification_score("35238000AB0297")

        assert score is not None
        assert isinstance(score, DensificationScore)
        assert score.id_parcelle == "35238000AB0297"
        assert score.ces_actuel >= Decimal("0.0")
        assert score.ces_potentiel == Decimal("0.40")

    async def test_get_densification_score_inexistant(self, duckdb_repo):
        """Test récupération score inexistant."""
        score = await duckdb_repo.get_densification_score("00000000XX9999")

        assert score is None

    async def test_get_top_densification_opportunities(self, duckdb_repo):
        """Test récupération top opportunités."""
        opportunities = await duckdb_repo.get_top_densification_opportunities(
            code_commune="35238",
            limit=5
        )

        assert isinstance(opportunities, list)
        assert len(opportunities) <= 5

        # Vérifier que tous sont FORT
        for opp in opportunities:
            assert opp.categorie == "FORT"

        # Vérifier tri par surface_constructible_restante DESC
        if len(opportunities) > 1:
            for i in range(len(opportunities) - 1):
                assert (opportunities[i].surface_constructible_restante >=
                        opportunities[i+1].surface_constructible_restante)


@pytest.fixture
def duckdb_repo(tmp_path):
    """DuckDBLandRepository sur une base temporaire au contenu maitrise.

    La fixture pointait auparavant sur `data/foncier.duckdb` — un fichier de
    69 Go, absent de toute CI, dont le contenu variait. D'ou des tests soit
    silencieusement passants (`if score is not None:`), soit en echec sur des
    donnees reelles malformees (identifiants de parcelle a 12 caracteres au
    lieu de 14). On construit desormais exactement ce que l'on affirme.
    """
    import duckdb

    from app.repositories.duckdb_repository import DuckDBLandRepository

    db_path = tmp_path / "dept35.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute("""
        CREATE TABLE densification_scores (
            id_parcelle VARCHAR,
            code_commune VARCHAR,
            surface_parcelle_m2 DOUBLE,
            surface_plancher_m2 DOUBLE,
            ces_actuel DOUBLE,
            ces_potentiel DOUBLE,
            surface_constructible_restante DOUBLE,
            categorie VARCHAR
        )
    """)
    conn.execute("""
        INSERT INTO densification_scores VALUES
        ('35238000AB0297', '35238', 1000.0, 200.0, 0.20, 0.40, 200.0, 'FORT'),
        ('35238000AB0298', '35238',  800.0, 100.0, 0.125, 0.40, 220.0, 'FORT'),
        ('35238000AB0299', '35238',  500.0,  50.0, 0.10, 0.40, 150.0, 'FORT'),
        ('35238000AB0300', '35238',  600.0, 240.0, 0.40, 0.40,   0.0, 'SATURE')
    """)
    conn.close()

    repo = DuckDBLandRepository(db_path)
    yield repo
    repo.close()
