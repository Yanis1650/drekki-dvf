"""Lectures de la table `enrichment_scores`."""

from decimal import Decimal

from app.domain.models import EnrichmentScore


class PoiEnrichmentMixin:
    """Scores d'enrichissement, par parcelle ou par commune."""

    async def get_enrichment_by_parcelle(self, id_parcelle: str) -> EnrichmentScore | None:
        """Retrieve enrichment score for a parcel."""
        conn = self._get_connection()
        result = conn.execute(
            """
            SELECT id_parcelle, schools_score, transport_score,
                   nuisances_score, green_spaces_score
            FROM enrichment_scores
            WHERE id_parcelle = ?
            """,
            [id_parcelle],
        ).fetchone()

        if result is None:
            return None

        return EnrichmentScore(
            id_parcelle=result[0],
            schools_score=Decimal(str(result[1])),
            transport_score=Decimal(str(result[2])),
            nuisances_score=Decimal(str(result[3])),
            green_spaces_score=Decimal(str(result[4])),
        )

    async def get_enrichments_by_commune(self, code_commune: str) -> list[EnrichmentScore]:
        """Retrieve all enrichment scores for a commune."""
        conn = self._get_connection()
        results = conn.execute(
            """
            SELECT e.id_parcelle, e.schools_score, e.transport_score,
                   e.nuisances_score, e.green_spaces_score
            FROM enrichment_scores e
            JOIN parcelles p ON e.id_parcelle = p.id_parcelle
            WHERE p.code_commune = ?
            """,
            [code_commune],
        ).fetchall()

        return [
            EnrichmentScore(
                id_parcelle=r[0],
                schools_score=Decimal(str(r[1])),
                transport_score=Decimal(str(r[2])),
                nuisances_score=Decimal(str(r[3])),
                green_spaces_score=Decimal(str(r[4])),
            )
            for r in results
        ]
