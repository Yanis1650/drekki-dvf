"""Fan-out de l'enrichissement dans la recherche DVF.

La recherche enrichie calculait un score par mutation — jusqu'a mille par
requete, chacune declenchant six requetes spatiales — et le faisait sur la
boucle d'evenements, `calculate_enrichment` etant declaree `async` sans jamais
rien attendre. Une seule recherche enrichie gelait donc toute l'API.

Le score ne depend que des coordonnees, et `EnrichmentScoreResponse` ne porte
aucun identifiant de parcelle : mutualiser les positions identiques ne change
rien a la reponse rendue. La memoisation reste exacte — aucune grille, aucun
arrondi, donc aucun score emprunte a un point voisin.
"""

from decimal import Decimal

from app.api.v1.endpoints.land_search import _score_positions


class _FakeService:
    """Compte les positions reellement scorees."""

    def __init__(self):
        self.calls: list[tuple[Decimal, Decimal]] = []

    def calculate_enrichment_blocking(self, latitude, longitude, parcelle_id=None):
        self.calls.append((latitude, longitude))
        return type(
            "Score",
            (),
            {
                "schools_score": Decimal("5"),
                "transport_score": Decimal("5"),
                "transit_score": Decimal("5"),
                "nuisances_score": Decimal("5"),
                "green_spaces_score": Decimal("5"),
                "global_score": Decimal("5"),
            },
        )()


HERE = (Decimal("48.1173"), Decimal("-1.6778"))
THERE = (Decimal("48.1180"), Decimal("-1.6790"))


def test_une_position_distincte_n_est_scoree_qu_une_fois():
    service = _FakeService()
    scores = _score_positions(service, [HERE, THERE])

    assert len(service.calls) == 2
    assert set(scores) == {HERE, THERE}


def test_le_corps_du_calcul_est_synchrone():
    """Il doit pouvoir partir dans un thread : une coroutine ne le pourrait pas."""
    import inspect

    from app.services.enrichment import EnrichmentService

    assert not inspect.iscoroutinefunction(EnrichmentService.calculate_enrichment_blocking)
    assert inspect.iscoroutinefunction(EnrichmentService.calculate_enrichment)
