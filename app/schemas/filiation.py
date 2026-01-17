"""Pydantic schemas for filiation API responses."""

from datetime import date

from pydantic import BaseModel, Field


class AncestorInfo(BaseModel):
    """Information about a parcel ancestor."""

    id_parcelle: str = Field(description="Parcel ID (section + number)")
    date_division: date | None = Field(None, description="Date of division operation")
    nature_operation: str | None = Field(None, description="Type of operation (1-8)")


class FiliationResponse(BaseModel):
    """Response schema for parcel filiation endpoint."""

    id_parcelle: str = Field(description="Queried parcel ID")
    filiation_summary: str = Field(
        description="Human-readable filiation summary for UI display"
    )
    depth: int = Field(description="Number of generations traced back")
    ancestors: list[AncestorInfo] = Field(
        default_factory=list, description="List of ancestors from oldest to newest"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id_parcelle": "AC0214",
                "filiation_summary": "Issue de la parcelle AC0026 (divisée en 1990)",
                "depth": 1,
                "ancestors": [
                    {
                        "id_parcelle": "AC0026",
                        "date_division": "1990-08-13",
                        "nature_operation": "1",
                    }
                ],
            }
        }
