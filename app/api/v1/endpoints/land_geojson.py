"""Land GeoJSON endpoints."""

import json
import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import RepositoryDep

logger = logging.getLogger(__name__)

router = APIRouter(tags=["land", "geojson"])


@router.get("/geojson")
async def get_transactions_geojson(
    repository: RepositoryDep,
    bbox: Annotated[str, Query(description="min_lon,min_lat,max_lon,max_lat")],
) -> dict:
    """Get DVF transactions as GeoJSON Point features."""
    try:
        coords = [float(x) for x in bbox.split(",")]
        if len(coords) != 4:
            raise ValueError("Invalid bbox format")
        min_lon, min_lat, max_lon, max_lat = coords
        if (max_lon - min_lon) > 2.0 or (max_lat - min_lat) > 2.0:
            raise HTTPException(status_code=400, detail="Area too large. Please zoom in.")
        geojson_str = await repository.get_transactions_geojson(
            min_x=min_lon, min_y=min_lat, max_x=max_lon, max_y=max_lat, limit=2000
        )
        return json.loads(geojson_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid bbox coordinates")
    except HTTPException:
        raise
    except Exception:
        logger.exception("Transactions GeoJSON query failed for bbox=%s", bbox)
        raise HTTPException(status_code=500, detail="Transactions query failed")


@router.get("/parcelles")
async def get_parcelles_geojson(
    repository: RepositoryDep,
    bbox: Annotated[str, Query(description="min_lon,min_lat,max_lon,max_lat")],
    filter: Annotated[
        str | None,
        Query(description="Filter: 'zan' (Fort potentiel ZAN) or 'recent' (Ventes < 2 ans)"),
    ] = None,
) -> dict:
    """Get cadastral parcels as GeoJSON Polygon features."""
    try:
        coords = [float(x) for x in bbox.split(",")]
        if len(coords) != 4:
            raise ValueError("Invalid bbox format")
        min_lon, min_lat, max_lon, max_lat = coords
        if (max_lon - min_lon) > 0.5 or (max_lat - min_lat) > 0.5:
            raise HTTPException(status_code=400, detail="Area too large. Zoom in.")
        if filter and filter not in ("zan", "recent"):
            raise HTTPException(status_code=400, detail="Filter must be 'zan' or 'recent'")
        geojson_str = await repository.get_parcelles_geojson(
            min_x=min_lon, min_y=min_lat, max_x=max_lon, max_y=max_lat, limit=1000, filter=filter
        )
        return json.loads(geojson_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid bbox coordinates")
    except HTTPException:
        raise
    except Exception:
        logger.exception("Parcelles GeoJSON query failed for bbox=%s", bbox)
        raise HTTPException(status_code=500, detail="Parcelles query failed")
