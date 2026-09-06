"""Response schemas for transaction endpoints.

Separates API contracts from domain models (SOLID - Interface Segregation).
"""

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class TransactionResponse(BaseModel):
    """Single transaction response."""

    id_mutation: str
    date_mutation: date
    nature_mutation: str
    valeur_fonciere: Decimal
    code_commune: str
    id_parcelle: str
    type_local: str | None = None
    surface_reelle_bati: Decimal | None = None
    nombre_pieces: int | None = None


class EnrichmentScoreResponse(BaseModel):
    """Enrichment scores for a location."""

    education_score: Decimal = Field(ge=0, le=10)
    transport_score: Decimal = Field(ge=0, le=10)
    transit_score: Decimal = Field(ge=0, le=10, default=Decimal("5.0"))
    nuisances_score: Decimal = Field(ge=0, le=10, default=Decimal("5.0"))
    green_spaces_score: Decimal = Field(ge=0, le=10, default=Decimal("5.0"))
    global_score: Decimal = Field(ge=0, le=10)


class EnrichmentDetailResponse(BaseModel):
    """Detailed enrichment with breakdowns."""

    global_score: Decimal
    education: dict[str, Any] = {}
    transport: dict[str, Any] = {}


class MutationResponse(BaseModel):
    """Aggregated mutation response (Mericskay methodology)."""

    id_mutation: str
    date_mutation: str
    nature_mutation: str
    valeur_fonciere: Decimal
    code_commune: str
    parcelles: list[str]
    surface_habitable_totale: Decimal
    nombre_locaux: int
    type_local: str | None = None
    prix_m2: Decimal | None = None
    longitude: float | None = None
    latitude: float | None = None
    is_outlier: bool = False


class EnrichedMutationResponse(BaseModel):
    """Mutation with enrichment scores."""

    mutation: MutationResponse
    enrichment: EnrichmentScoreResponse | None = None


class PriceStatsResponse(BaseModel):
    """Price statistics for a commune."""

    code_commune: str
    min_price_m2: Decimal
    max_price_m2: Decimal
    median_price_m2: Decimal
    avg_price_m2: Decimal
    mutations_count: int


class SearchResultResponse(BaseModel):
    """Spatial search result."""

    center_lat: float
    center_lon: float
    radius_meters: int
    mutations_count: int
    avg_price_m2: Decimal | None = None
    mutations: list[MutationResponse]


class EnrichedSearchResultResponse(BaseModel):
    """Spatial search result with enrichment."""

    center_lat: float
    center_lon: float
    radius_meters: int
    mutations_count: int
    avg_price_m2: Decimal | None = None
    enrichment_available: bool = Field(
        default=True,
        description=(
            "False quand les POI OpenStreetMap ne sont pas chargés dans cette "
            "base : les champs `enrichment` et `location_enrichment` sont alors "
            "nuls. À distinguer d'un score réellement bas."
        ),
    )
    location_enrichment: EnrichmentDetailResponse | None = None
    mutations: list[EnrichedMutationResponse]


class CommuneAnalysisResponse(BaseModel):
    """Full commune analysis response."""

    code_commune: str
    strategy: str
    date_range: dict[str, date | None]
    statistics: PriceStatsResponse
    mutations_count: int
    mutations: list[MutationResponse]


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    database: str = "connected"
    version: str = "0.1.0"


class ReadinessResponse(BaseModel):
    """Etat des donnees coeur necessaires au service de l'application."""

    status: str = "ready"
    database: str = "duckdb"
    missing_tables: list[str]

