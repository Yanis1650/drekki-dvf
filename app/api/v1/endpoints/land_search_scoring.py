"""Memoisation du score d'enrichissement pour la recherche enrichie."""

from decimal import Decimal

from app.schemas import EnrichmentScoreResponse
from app.services.enrichment import EnrichmentService


def _score_positions(
    enrichment_service: "EnrichmentService", positions: list[tuple[Decimal, Decimal]]
) -> dict[tuple[Decimal, Decimal], EnrichmentScoreResponse]:
    """Score une position distincte a la fois, hors de la boucle d'evenements.

    Deux couts se cumulaient ici. L'enrichissement etait calcule par mutation —
    jusqu'a mille par requete, chacune declenchant six requetes spatiales — et
    il s'executait sur la boucle d'evenements, donc une seule recherche
    enrichie gelait toute l'API.

    La memoisation porte sur les coordonnees exactes : DVF pose souvent
    plusieurs mutations au meme point (un immeuble, plusieurs lots). Arrondir a
    une grille reduirait davantage le nombre d'appels, mais rendrait le score
    d'un point voisin — une valeur que la source n'a jamais produite. Le vrai
    remede au N+1 restant est une jointure spatiale unique cote DuckDB, qui
    demande un contrat de repository que le pipeline POI ne fournit pas encore.
    """
    scores: dict[tuple[Decimal, Decimal], EnrichmentScoreResponse] = {}
    for latitude, longitude in positions:
        computed = enrichment_service.calculate_enrichment_blocking(
            latitude=latitude, longitude=longitude
        )
        scores[(latitude, longitude)] = EnrichmentScoreResponse(
            education_score=computed.schools_score,
            transport_score=computed.transport_score,
            transit_score=computed.transit_score,
            nuisances_score=computed.nuisances_score,
            green_spaces_score=computed.green_spaces_score,
            global_score=computed.global_score,
        )
    return scores
