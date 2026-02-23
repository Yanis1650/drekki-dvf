"""Land parcelle endpoints (search, fiche, densification)."""

import csv
import io
import logging
from typing import Annotated

from fastapi import HTTPException, Query
from fastapi.responses import Response

from app.api.deps import RepositoryDep

logger = logging.getLogger(__name__)

router = APIRouter(tags=["land", "parcelles"])


@router.get("/parcelles/search")
async def search_parcelles(
    repository: RepositoryDep,
    code_commune: Annotated[str | None, Query()] = None,
    categorie: Annotated[str | None, Query()] = None,
    confidence_min: Annotated[float, Query(ge=0, le=1)] = 0.0,
    prix_m2_max: Annotated[float | None, Query()] = None,
    surface_min: Annotated[float | None, Query()] = None,
    annee_min: Annotated[int | None, Query()] = None,
    export_csv: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
):
    """Multi-criteria parcel search with CSV export."""
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
                headers={"Content-Disposition": "attachment; filename=export_foncier.csv"},
            )
        return {"count": len(rows), "results": rows}
    except Exception:
        logger.exception("Parcelles search failed")
        raise HTTPException(status_code=500, detail="Search failed")


@router.get("/parcelles/{id_parcelle}/fiche")
async def get_parcel_fiche(id_parcelle: str, repository: RepositoryDep):
    """Complete parcel fiche: DVF + BDNB + densification + confidence."""
    try:
        fiche = await repository.get_parcelle_fiche(id_parcelle)
        if fiche is None:
            raise HTTPException(status_code=404, detail=f"Parcelle {id_parcelle} not found")
        return fiche
    except HTTPException:
        raise
    except Exception:
        logger.exception("Fiche query failed for parcelle %s", id_parcelle)
        raise HTTPException(status_code=500, detail="Fiche query failed")


@router.get("/parcelles/{id_parcelle}/densification")
async def get_parcel_densification(id_parcelle: str, repository: RepositoryDep):
    """Get densification score for a parcel (CES, potential)."""
    try:
        score = await repository.get_densification_score(id_parcelle)
        if score is None:
            raise HTTPException(status_code=404, detail="Densification score not found")
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
    except Exception:
        logger.exception("Densification query failed for parcelle %s", id_parcelle)
        raise HTTPException(status_code=500, detail="Densification query failed")


@router.get("/communes/{code_commune}/densification/top")
async def get_top_densification_opportunities(
    code_commune: str,
    repository: RepositoryDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """Top densification opportunities for a commune."""
    try:
        opportunities = await repository.get_top_densification_opportunities(
            code_commune=code_commune, limit=limit
        )
        return {
            "commune": code_commune,
            "count": len(opportunities),
            "opportunities": [
                {
                    "id_parcelle": s.id_parcelle,
                    "surface_parcelle_m2": float(s.surface_parcelle_m2),
                    "surface_plancher_m2": float(s.surface_plancher_m2),
                    "ces_actuel": float(s.ces_actuel),
                    "ces_potentiel": float(s.ces_potentiel),
                    "potentiel_densification": float(s.potentiel_densification),
                    "surface_constructible_restante": float(s.surface_constructible_restante),
                    "categorie": s.categorie,
                }
                for s in opportunities
            ],
        }
    except Exception:
        logger.exception("Top densification failed for commune %s", code_commune)
        raise HTTPException(status_code=500, detail="Top opportunities query failed")
