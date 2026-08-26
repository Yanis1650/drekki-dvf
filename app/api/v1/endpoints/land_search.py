"""Land search and commune endpoints."""

import logging
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import DvfAnalyzerDep, EnrichmentDep, RepositoryDep
from app.schemas import (
    EnrichedMutationResponse,
    EnrichedSearchResultResponse,
    EnrichmentDetailResponse,
    EnrichmentScoreResponse,
    MutationResponse,
    PriceStatsResponse,
    SearchResultResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["land", "search"])


@router.get("/search", response_model=SearchResultResponse)
async def search_transactions(
    repository: RepositoryDep,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    radius: Annotated[int, Query(ge=100, le=50000)] = 1000,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> SearchResultResponse:
    """Search transactions within a radius (WGS84)."""
    try:
        mutations = await repository.get_mutations_in_radius(
            lat=lat, lon=lon, radius_meters=radius,
            date_from=date_from, date_to=date_to, limit=limit,
        )
        response_mutations = []
        total_price = Decimal("0")
        price_count = 0
        for m in mutations:
            response_mutations.append(MutationResponse(
                id_mutation=m.id_mutation,
                date_mutation=str(m.date_mutation),
                nature_mutation=m.nature_mutation.value,
                valeur_fonciere=m.valeur_fonciere,
                code_commune=m.code_commune,
                parcelles=list(m.parcelles),
                surface_habitable_totale=m.surface_habitable_totale,
                nombre_locaux=m.nombre_locaux,
                type_local=m.type_local.value if m.type_local else None,
                prix_m2=m.prix_m2,
                longitude=m.longitude,
                latitude=m.latitude,
                is_outlier=m.is_outlier,
            ))
            if m.prix_m2 and not m.is_outlier:
                total_price += m.prix_m2
                price_count += 1
        return SearchResultResponse(
            center_lat=lat, center_lon=lon, radius_meters=radius,
            mutations_count=len(response_mutations),
            avg_price_m2=total_price / price_count if price_count > 0 else None,
            mutations=response_mutations,
        )
    except Exception:
        logger.exception("Search failed for lat=%s lon=%s radius=%s", lat, lon, radius)
        raise HTTPException(status_code=500, detail="Search failed")


@router.get("/search/enriched", response_model=EnrichedSearchResultResponse)
async def search_transactions_enriched(
    repository: RepositoryDep,
    enrichment_service: EnrichmentDep,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    radius: Annotated[int, Query(ge=100, le=50000)] = 1000,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> EnrichedSearchResultResponse:
    """Search transactions with enrichment scores."""
    try:
        mutations = await repository.get_mutations_in_radius(
            lat=lat, lon=lon, radius_meters=radius,
            date_from=date_from, date_to=date_to, limit=limit,
        )

        # Les POI OSM ne sont pas charges dans toutes les bases. Quand ils
        # manquent, on renvoie les transactions sans scores plutot que des
        # scores neutres (5/10) indiscernables d'une vraie mesure.
        enrichment_available = enrichment_service.is_available
        if not enrichment_available:
            logger.info(
                "POI non charges pour cette base — recherche renvoyee sans enrichissement."
            )

        location_enrichment = (
            await enrichment_service.calculate_enrichment_detailed(latitude=lat, longitude=lon)
            if enrichment_available
            else None
        )
        enriched_mutations = []
        total_price = Decimal("0")
        price_count = 0
        for m in mutations:
            mutation_response = MutationResponse(
                id_mutation=m.id_mutation,
                date_mutation=str(m.date_mutation),
                nature_mutation=m.nature_mutation.value,
                valeur_fonciere=m.valeur_fonciere,
                code_commune=m.code_commune,
                parcelles=list(m.parcelles),
                surface_habitable_totale=m.surface_habitable_totale,
                nombre_locaux=m.nombre_locaux,
                type_local=m.type_local.value if m.type_local else None,
                prix_m2=m.prix_m2,
                longitude=m.longitude,
                latitude=m.latitude,
                is_outlier=m.is_outlier,
            )
            enrichment = None
            if enrichment_available and m.latitude and m.longitude:
                ed = await enrichment_service.calculate_enrichment(
                    latitude=m.latitude, longitude=m.longitude,
                    parcelle_id=m.parcelles[0] if m.parcelles else None,
                )
                enrichment = EnrichmentScoreResponse(
                    education_score=ed.schools_score,
                    transport_score=ed.transport_score,
                    transit_score=ed.transit_score,
                    nuisances_score=ed.nuisances_score,
                    green_spaces_score=ed.green_spaces_score,
                    global_score=ed.global_score,
                )
            enriched_mutations.append(EnrichedMutationResponse(
                mutation=mutation_response,
                enrichment=enrichment,
            ))
            if m.prix_m2 and not m.is_outlier:
                total_price += m.prix_m2
                price_count += 1
        return EnrichedSearchResultResponse(
            center_lat=lat, center_lon=lon, radius_meters=radius,
            mutations_count=len(enriched_mutations),
            avg_price_m2=total_price / price_count if price_count > 0 else None,
            enrichment_available=enrichment_available,
            location_enrichment=(
                EnrichmentDetailResponse(
                    global_score=location_enrichment["global_score"],
                    education=location_enrichment.get("education", {}),
                    transport=location_enrichment.get("transport", {}),
                )
                if location_enrichment is not None
                else None
            ),
            mutations=enriched_mutations,
        )
    except Exception:
        logger.exception("Enriched search failed for lat=%s lon=%s", lat, lon)
        raise HTTPException(status_code=500, detail="Enriched search failed")


@router.get("/commune/{code_commune}/stats", response_model=PriceStatsResponse)
async def get_commune_stats(
    code_commune: str,
    analyzer: DvfAnalyzerDep,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> PriceStatsResponse:
    """Get price statistics for a commune."""
    try:
        stats = await analyzer.get_price_statistics(
            code_commune=code_commune, date_from=date_from, date_to=date_to,
        )
        mutations = await analyzer._transaction_repo.get_mutations_by_commune(
            code_commune, date_from, date_to
        )
        return PriceStatsResponse(
            code_commune=code_commune,
            min_price_m2=stats.get("min_price_m2", Decimal("0")),
            max_price_m2=stats.get("max_price_m2", Decimal("0")),
            median_price_m2=stats.get("median_price_m2", Decimal("0")),
            avg_price_m2=stats.get("avg_price_m2", Decimal("0")),
            mutations_count=len(mutations),
        )
    except Exception:
        logger.exception("Stats query failed for commune %s", code_commune)
        raise HTTPException(status_code=500, detail="Stats query failed")


@router.get("/commune/{code_commune}", response_model=list[MutationResponse])
async def get_commune_mutations(
    code_commune: str,
    repository: RepositoryDep,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[MutationResponse]:
    """Get mutations for a commune."""
    try:
        mutations = await repository.get_mutations_by_commune(
            code_commune, date_from, date_to,
        )
        def to_resp(m):
            return MutationResponse(
                id_mutation=m.id_mutation, date_mutation=str(m.date_mutation),
                nature_mutation=m.nature_mutation.value, valeur_fonciere=m.valeur_fonciere,
                code_commune=m.code_commune, parcelles=list(m.parcelles),
                surface_habitable_totale=m.surface_habitable_totale,
                nombre_locaux=m.nombre_locaux,
                type_local=m.type_local.value if m.type_local else None,
                prix_m2=m.prix_m2,
                is_outlier=m.is_outlier,
            )
        return [to_resp(m) for m in mutations[:limit]]
    except Exception:
        logger.exception("Commune mutations query failed for %s", code_commune)
        raise HTTPException(status_code=500, detail="Query failed")
