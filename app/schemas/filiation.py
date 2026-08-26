"""Pydantic schemas for filiation API responses."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class AncestorInfo(BaseModel):
    """Information about a parcel ancestor in the linear chain."""

    id_parcelle: str = Field(description="Parcel ID (section + number)")
    date_division: date | None = Field(None, description="Date of division operation")
    nature_operation: str | None = Field(None, description="Type of operation (1-8)")
    coherence_geo: str = Field(
        default="NON_VERIFIABLE",
        description=(
            "Geometric coherence between this parcel and its parent: "
            "'OK' (≥80%), 'PARTIELLE' (≥30%), 'DOUTEUSE' (<30%), 'NON_VERIFIABLE'."
        ),
    )


class FiliationNodeResponse(BaseModel):
    """Recursive tree node for the /filiation/{id} response.

    Mirrors FiliationNode (domain model) as a serializable API schema.
    truncated=True signals that the sub-tree was cut at this node (depth
    limit reached or cycle detected); the frontend should render a visual
    indicator (e.g., ⚠ « historique incomplet »).
    """

    id_parcelle: str = Field(description="Parcel ID (section + number)")
    date_division: date | None = Field(None, description="Date of division operation")
    nature_operation: str | None = Field(None, description="Type of operation (1-8)")
    depth: int = Field(description="Depth in the ancestor tree (0 = queried parcel)")
    truncated: bool = Field(
        default=False,
        description=(
            "True if tree reconstruction stopped here. "
            "Indicates incomplete history (depth limit or cycle)."
        ),
    )
    coherence_geo: str = Field(
        default="NON_VERIFIABLE",
        description=(
            "Geometric coherence with parent parcel: "
            "'OK', 'PARTIELLE', 'DOUTEUSE', or 'NON_VERIFIABLE'."
        ),
    )
    parent: Optional["FiliationNodeResponse"] = Field(
        None, description="Parent node (recursive)"
    )


FiliationNodeResponse.model_rebuild()


class FiliationResponse(BaseModel):
    """Response schema for parcel filiation endpoint."""

    id_parcelle: str = Field(description="Queried parcel ID")
    filiation_summary: str = Field(
        description="Human-readable filiation summary for UI display"
    )
    depth: int = Field(description="Number of generations traced back")
    truncated: bool = Field(
        default=False,
        description="True if at least one node in the tree was truncated.",
    )
    ancestors: list[AncestorInfo] = Field(
        default_factory=list,
        description="Linear ancestor chain from oldest to newest",
    )
    tree: FiliationNodeResponse | None = Field(
        None,
        description="Full recursive tree (same data as ancestors but structured)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id_parcelle": "AC0214",
                "filiation_summary": "Issue de la parcelle AC0026 (divisée en 1990)",
                "depth": 1,
                "truncated": False,
                "ancestors": [
                    {
                        "id_parcelle": "AC0026",
                        "date_division": "1990-08-13",
                        "nature_operation": "1",
                        "coherence_geo": "OK",
                    }
                ],
                "tree": None,
            }
        }
