"""Endpoints par commune : statistiques de prix et mutations."""

import logging
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import DvfAnalyzerDep, RepositoryDep
from app.infrastructure.unavailable import ResourceUnavailableError
from app.schemas import MutationResponse, PriceStatsResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["land", "search"])


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
    except ResourceUnavailableError:
        # 503 explicite : donnee non chargee ou extension absente.
        # Sans cette reprise, le `except Exception` ci-dessous la
        # transformerait en 500 « erreur serveur ».
        raise
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
    except ResourceUnavailableError:
        # 503 explicite : donnee non chargee ou extension absente.
        # Sans cette reprise, le `except Exception` ci-dessous la
        # transformerait en 500 « erreur serveur ».
        raise
    except Exception:
        logger.exception("Commune mutations query failed for %s", code_commune)
        raise HTTPException(status_code=500, detail="Query failed")
