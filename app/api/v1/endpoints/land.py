"""Land and transaction endpoints.

Provides spatial search and DVF analysis via REST API.
"""

import logging
from datetime import date

logger = logging.getLogger(__name__)
from decimal import Decimal
from typing import Annotated

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.api.deps import (
    CreditCheckDep,
    DvfAnalyzerDep,
    EnrichmentDep,
    ReportDep,
    RepositoryDep,
    SettingsDep,
    get_user_repository,
)
from app.infrastructure.duckdb_pool import get_pool
from app.repositories.user_repository import UserRepository
from app.schemas import (
    EnrichedMutationResponse,
    EnrichedSearchResultResponse,
    EnrichmentDetailResponse,
    EnrichmentScoreResponse,
    MutationResponse,
    PriceStatsResponse,
    SearchResultResponse,
)

router = APIRouter(prefix="/land", tags=["land", "transactions"])


@router.get("/search", response_model=SearchResultResponse)
async def search_transactions(
    repository: RepositoryDep,
    lat: Annotated[float, Query(description="Latitude WGS84", ge=-90, le=90)],
    lon: Annotated[float, Query(description="Longitude WGS84", ge=-180, le=180)],
    radius: Annotated[int, Query(description="Radius in meters", ge=100, le=50000)] = 1000,
    date_from: Annotated[date | None, Query(description="Start date filter")] = None,
    date_to: Annotated[date | None, Query(description="End date filter")] = None,
    limit: Annotated[int, Query(description="Max results", ge=1, le=1000)] = 100,
) -> SearchResultResponse:
    """Search transactions within a radius of a point.

    Uses optimized Haversine formula with bounding box pre-filter.
    Coordinates are in WGS84 (EPSG:4326).
    """
    try:
        # Use repository method for clean separation
        mutations = await repository.get_mutations_in_radius(
            lat=lat,
            lon=lon,
            radius_meters=radius,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )

        # Convert to response models and calculate avg price
        response_mutations = []
        total_price = Decimal("0")
        price_count = 0

        for m in mutations:
            prix_m2 = m.prix_m2
            response_mutations.append(MutationResponse(
                id_mutation=m.id_mutation,
                date_mutation=str(m.date_mutation),
                nature_mutation=m.nature_mutation.value,
                valeur_fonciere=m.valeur_fonciere,
                code_commune=m.code_commune,
                parcelles=list(m.parcelles),
                surface_habitable_totale=m.surface_habitable_totale,
                nombre_locaux=m.nombre_locaux,
                prix_m2=prix_m2,
                longitude=m.longitude,
                latitude=m.latitude,
            ))
            if prix_m2:
                total_price += prix_m2
                price_count += 1

        avg_price = total_price / price_count if price_count > 0 else None

        return SearchResultResponse(
            center_lat=lat,
            center_lon=lon,
            radius_meters=radius,
            mutations_count=len(response_mutations),
            avg_price_m2=avg_price,
            mutations=response_mutations,
        )

    except Exception as e:
        logger.exception("Search failed for lat=%s lon=%s radius=%s", lat, lon, radius)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/search/enriched", response_model=EnrichedSearchResultResponse)
async def search_transactions_enriched(
    repository: RepositoryDep,
    enrichment_service: EnrichmentDep,
    lat: Annotated[float, Query(description="Latitude WGS84", ge=-90, le=90)],
    lon: Annotated[float, Query(description="Longitude WGS84", ge=-180, le=180)],
    radius: Annotated[int, Query(description="Radius in meters", ge=100, le=50000)] = 1000,
    date_from: Annotated[date | None, Query(description="Start date filter")] = None,
    date_to: Annotated[date | None, Query(description="End date filter")] = None,
    limit: Annotated[int, Query(description="Max results", ge=1, le=1000)] = 100,
) -> EnrichedSearchResultResponse:
    """Search transactions with enrichment scores.

    Returns DVF data (Mericskay) + EnrichmentScore (Education, Transport).
    """
    try:
        # Get mutations
        mutations = await repository.get_mutations_in_radius(
            lat=lat,
            lon=lon,
            radius_meters=radius,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )

        # Calculate location enrichment (for search center)
        location_enrichment = await enrichment_service.calculate_enrichment_detailed(
            latitude=lat,
            longitude=lon,
        )

        # Build enriched responses
        enriched_mutations = []
        total_price = Decimal("0")
        price_count = 0

        for m in mutations:
            prix_m2 = m.prix_m2

            # Create mutation response
            mutation_response = MutationResponse(
                id_mutation=m.id_mutation,
                date_mutation=str(m.date_mutation),
                nature_mutation=m.nature_mutation.value,
                valeur_fonciere=m.valeur_fonciere,
                code_commune=m.code_commune,
                parcelles=list(m.parcelles),
                surface_habitable_totale=m.surface_habitable_totale,
                nombre_locaux=m.nombre_locaux,
                prix_m2=prix_m2,
                longitude=m.longitude,
                latitude=m.latitude,
            )

            # Calculate enrichment for this mutation's location
            enrichment = None
            if m.latitude and m.longitude:
                enrichment_data = await enrichment_service.calculate_enrichment(
                    latitude=m.latitude,
                    longitude=m.longitude,
                    parcelle_id=m.parcelles[0] if m.parcelles else None,
                )
                enrichment = EnrichmentScoreResponse(
                    education_score=enrichment_data.schools_score,
                    transport_score=enrichment_data.transport_score,
                    nuisances_score=enrichment_data.nuisances_score,
                    green_spaces_score=enrichment_data.green_spaces_score,
                    global_score=enrichment_data.global_score,
                )

            enriched_mutations.append(EnrichedMutationResponse(
                mutation=mutation_response,
                enrichment=enrichment,
            ))

            if prix_m2:
                total_price += prix_m2
                price_count += 1

        avg_price = total_price / price_count if price_count > 0 else None

        return EnrichedSearchResultResponse(
            center_lat=lat,
            center_lon=lon,
            radius_meters=radius,
            mutations_count=len(enriched_mutations),
            avg_price_m2=avg_price,
            location_enrichment=EnrichmentDetailResponse(
                global_score=location_enrichment["global_score"],
                education=location_enrichment.get("education", {}),
                transport=location_enrichment.get("transport", {}),
            ),
            mutations=enriched_mutations,
        )

    except Exception as e:
        logger.exception("Enriched search failed for lat=%s lon=%s", lat, lon)
        raise HTTPException(status_code=500, detail=f"Enriched search failed: {str(e)}")


@router.get("/commune/{code_commune}/stats", response_model=PriceStatsResponse)
async def get_commune_stats(
    code_commune: str,
    analyzer: DvfAnalyzerDep,
    date_from: Annotated[date | None, Query(description="Start date")] = None,
    date_to: Annotated[date | None, Query(description="End date")] = None,
) -> PriceStatsResponse:
    """Get price statistics for a commune."""
    try:
        stats = await analyzer.get_price_statistics(
            code_commune=code_commune,
            date_from=date_from,
            date_to=date_to,
        )

        # Get count
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

    except Exception as e:
        logger.exception("Stats query failed for commune %s", code_commune)
        raise HTTPException(status_code=500, detail=f"Stats query failed: {str(e)}")


@router.get("/commune/{code_commune}", response_model=list[MutationResponse])
async def get_commune_mutations(
    code_commune: str,
    repository: RepositoryDep,
    date_from: Annotated[date | None, Query(description="Start date")] = None,
    date_to: Annotated[date | None, Query(description="End date")] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[MutationResponse]:
    """Get mutations for a specific commune."""
    try:
        mutations = await repository.get_mutations_by_commune(
            code_commune=code_commune,
            date_from=date_from,
            date_to=date_to,
        )

        return [
            MutationResponse(
                id_mutation=m.id_mutation,
                date_mutation=str(m.date_mutation),
                nature_mutation=m.nature_mutation.value,
                valeur_fonciere=m.valeur_fonciere,
                code_commune=m.code_commune,
                parcelles=list(m.parcelles),
                surface_habitable_totale=m.surface_habitable_totale,
                nombre_locaux=m.nombre_locaux,
                prix_m2=m.prix_m2,
            )
            for m in mutations[:limit]
        ]

    except Exception as e:
        logger.exception("Commune mutations query failed for %s", code_commune)
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.get("/report/{id_mutation}")
async def generate_mutation_report(
    id_mutation: str,
    report_service: ReportDep,
    user: "CreditCheckDep",  # Verifies balance >= 1
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    format: Annotated[str, Query(description="Output format: pdf or html")] = "html",
) -> Response:
    """Generate report for a mutation.
    
    Consumes 1 Credit.

    Returns a HTML document (PDF requires GTK on Windows).
    - Cadastral summary
    - Price analysis (Mericskay methodology)
    - Enrichment scores radar chart
    """
    try:
        content = await report_service.generate_report(id_mutation, format=format)

        # Debiter 1 crédit
        await user_repo.update_balance(user.id, -1, f"Report generated: {id_mutation}")
        await user_repo.session.commit()

        if format == "pdf":
            return Response(
                content=content,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="rapport_{id_mutation}.pdf"'
                },
            )
        else:
            return Response(
                content=content,
                media_type="text/html",
                headers={
                    "Content-Type": "text/html; charset=utf-8"
                },
            )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Report generation failed for mutation %s", id_mutation)
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")



@router.get("/geojson")
async def get_transactions_geojson(
    repository: RepositoryDep,
    bbox: Annotated[str, Query(description="Bounding box: min_lon,min_lat,max_lon,max_lat")],
) -> dict:
    """Get DVF transactions as GeoJSON Point features.
    
    Returns transaction points with properties: id, prix_m2, date, valeur_fonciere.
    Optimized for map display with clustering.
    """
    try:
        coords = [float(x) for x in bbox.split(",")]
        if len(coords) != 4:
            raise ValueError("Invalid bbox format")

        min_lon, min_lat, max_lon, max_lat = coords

        # Security: Limit area size (2.0 degrees ≈ 220km, reasonable for clustered view)
        if (max_lon - min_lon) > 2.0 or (max_lat - min_lat) > 2.0:
             raise HTTPException(status_code=400, detail="Area too large. Please zoom in.")

        geojson_str = await repository.get_transactions_geojson(
            min_x=min_lon,
            min_y=min_lat,
            max_x=max_lon,
            max_y=max_lat,
            limit=2000
        )

        import json
        return json.loads(geojson_str)

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid bbox coordinates")
    except Exception as e:
        logger.exception("Transactions GeoJSON query failed for bbox=%s", bbox)
        raise HTTPException(status_code=500, detail=f"Transactions query failed: {str(e)}")


@router.get("/parcelles")
async def get_parcelles_geojson(
    repository: RepositoryDep,
    bbox: Annotated[str, Query(description="Bounding box: min_lon,min_lat,max_lon,max_lat")],
) -> dict:
    """Get cadastral parcels as GeoJSON Polygon features with BDNB enrichment.
    
    Returns parcel polygons with properties: id_parcelle, dpe, annee_construction.
    Only fetches parcels for Dept 35 (real geometry available).
    Recommended to use only at zoom >= 15 for performance.
    """
    try:
        coords = [float(x) for x in bbox.split(",")]
        if len(coords) != 4:
            raise ValueError("Invalid bbox format")

        min_lon, min_lat, max_lon, max_lat = coords

        # Security: Limit area size to avoid massive queries
        # 0.2 degrees ≈ 22 km at equator (reasonable for zoom 13+)
        if (max_lon - min_lon) > 0.2 or (max_lat - min_lat) > 0.2:
             raise HTTPException(status_code=400, detail="Area too large. Please zoom in (zoom >= 13).")

        geojson_str = await repository.get_parcelles_geojson(
            min_x=min_lon,
            min_y=min_lat,
            max_x=max_lon,
            max_y=max_lat,
            limit=1000
        )

        import json
        return json.loads(geojson_str)

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid bbox coordinates")
    except Exception as e:
        logger.exception("Parcelles GeoJSON query failed for bbox=%s", bbox)
        raise HTTPException(status_code=500, detail=f"Parcelles query failed: {str(e)}")


@router.get("/parcelles/search")
async def search_parcelles(
    repository: RepositoryDep,
    code_commune: Annotated[str | None, Query(description="Code INSEE commune (5 chars)")] = None,
    categorie: Annotated[str | None, Query(description="FORT|MOYEN|FAIBLE|SATURE|NON_MUTABLE")] = None,
    confidence_min: Annotated[float, Query(description="Score confiance minimum (0-1)", ge=0, le=1)] = 0.0,
    prix_m2_max: Annotated[float | None, Query(description="Prix max au m2")] = None,
    surface_min: Annotated[float | None, Query(description="Surface parcelle min (m2)")] = None,
    annee_min: Annotated[int | None, Query(description="Annee mutation minimum")] = None,
    export_csv: Annotated[bool, Query(description="Retourner un fichier CSV")] = False,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
):
    """Recherche multi-criteres de parcelles avec filtres DVF + densification + confiance.

    Supporte l'export CSV pour analyse externe (tableur, SIG).
    """
    try:
        rows = await repository.search_parcelles(
            code_commune=code_commune,
            categorie=categorie,
            confidence_min=confidence_min,
            prix_m2_max=prix_m2_max,
            surface_min=surface_min,
            annee_min=annee_min,
            limit=limit,
        )

        if export_csv:
            if not rows:
                return Response(content="", media_type="text/csv")
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=rows[0].keys(), delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
            return Response(
                content=buf.getvalue(),
                media_type="text/csv; charset=utf-8",
                headers={
                    "Content-Disposition": "attachment; filename=export_foncier.csv",
                },
            )

        return {"count": len(rows), "results": rows}

    except Exception as e:
        logger.exception("Parcelles search failed")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/parcelles/{id_parcelle}/fiche")
async def get_parcel_fiche(
    id_parcelle: str,
    repository: RepositoryDep,
):
    """Fiche parcelle complete : DVF + BDNB + densification + confiance.

    Endpoint unique qui agrege toutes les sources de donnees pour une parcelle.
    Inclut le score de confiance et un warning explicite si les donnees
    sont partielles.
    """
    try:
        fiche = await repository.get_parcelle_fiche(id_parcelle)
        if fiche is None:
            raise HTTPException(
                status_code=404,
                detail=f"Aucune donnee trouvee pour la parcelle {id_parcelle}",
            )
        return fiche

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Fiche query failed for parcelle %s", id_parcelle)
        raise HTTPException(status_code=500, detail=f"Fiche query failed: {str(e)}")


@router.get("/parcelles/{id_parcelle}/densification")
async def get_parcel_densification(
    id_parcelle: str,
    repository: RepositoryDep,
):
    """Get densification potential score for a parcel.
    
    Returns CES (Coefficient d'Emprise au Sol) actuel, CES potentiel,
    and calculated densification potential (surface constructible restante).
    
    Used for ZAN (Zéro Artificialisation Nette) compliance analysis.
    """
    try:
        score = await repository.get_densification_score(id_parcelle)
        if score is None:
            raise HTTPException(status_code=404, detail=f"Densification score not found for parcel {id_parcelle}")

        return {
            "id_parcelle": score.id_parcelle,
            "surface_parcelle_m2": float(score.surface_parcelle_m2),
            "surface_plancher_m2": float(score.surface_plancher_m2),
            "ces_actuel": float(score.ces_actuel),
            "ces_potentiel": float(score.ces_potentiel),
            "potentiel_densification": float(score.potentiel_densification),
            "surface_constructible_restante": float(score.surface_constructible_restante),
            "categorie": score.categorie,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Densification query failed for parcelle %s", id_parcelle)
        raise HTTPException(status_code=500, detail=f"Densification query failed: {str(e)}")


@router.get("/communes/{code_commune}/densification/top")
async def get_top_densification_opportunities(
    code_commune: str,
    repository: RepositoryDep,
    limit: Annotated[int, Query(description="Max results", ge=1, le=100)] = 20,
):
    """Get top densification opportunities for a commune.
    
    Returns parcels with FORT potential (≥20% CES margin) sorted by
    surface_constructible_restante descending.
    
    Useful for identifying "dents creuses" (underutilized parcels).
    """
    try:
        opportunities = await repository.get_top_densification_opportunities(
            code_commune=code_commune,
            limit=limit
        )

        return {
            "commune": code_commune,
            "count": len(opportunities),
            "opportunities": [
                {
                    "id_parcelle": score.id_parcelle,
                    "surface_parcelle_m2": float(score.surface_parcelle_m2),
                    "surface_plancher_m2": float(score.surface_plancher_m2),
                    "ces_actuel": float(score.ces_actuel),
                    "ces_potentiel": float(score.ces_potentiel),
                    "potentiel_densification": float(score.potentiel_densification),
                    "surface_constructible_restante": float(score.surface_constructible_restante),
                    "categorie": score.categorie,
                }
                for score in opportunities
            ]
        }

    except Exception as e:
        logger.exception("Top densification opportunities query failed for commune %s", code_commune)
        raise HTTPException(status_code=500, detail=f"Top opportunities query failed: {str(e)}")


@router.get("/departements")
async def list_available_departments(settings: SettingsDep):
    """Liste les departements disponibles (bases DuckDB presentes)."""
    pool = get_pool(data_dir=settings.data_dir, legacy_path=settings.duckdb_path)
    depts = pool.available_depts
    return {
        "count": len(depts),
        "departements": depts,
        "mode": "multi_dept" if settings.multi_dept else "legacy",
    }

