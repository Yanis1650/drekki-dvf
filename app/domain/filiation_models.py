"""Domain models for parcel filiation.

Pure Pydantic V2 models with no external dependencies.
Represents administrative relationships between cadastral parcels.
"""

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DFINature(str, Enum):
    """Types de documents DFI (Documents de Filiation Informatisés)."""

    ARPENTAGE = "1"
    CROQUIS_CONSERVATION = "2"
    REMANIEMENT = "4"
    ARPENTAGE_NUMERIQUE = "5"
    LOTISSEMENT_NUMERIQUE = "6"
    LOTISSEMENT = "7"
    RENOVATION = "8"


class ParcelFiliation(BaseModel):
    """Relation mère-fille entre parcelles cadastrales.
    
    Représente une opération administrative (division, fusion, lotissement)
    qui transforme une ou plusieurs parcelles mères en parcelles filles.
    """

    id_dfi: str = Field(max_length=7, description="Identifiant unique du document DFI")
    code_departement: str = Field(max_length=3, description="Code département (ex: '035')")
    code_commune: str = Field(max_length=3, description="Code commune (ex: '001')")
    prefixe: str = Field(max_length=3, description="Préfixe de section (000 par défaut)")
    nature_dfi: DFINature = Field(description="Type d'opération cadastrale")
    date_validation: date = Field(description="Date de validation du document")
    numero_lot: str = Field(max_length=5, description="Numéro du lot d'analyse")
    parcelle_mere: str | None = Field(
        None, max_length=6, description="Section(2) + Numéro(4) de la parcelle mère"
    )
    parcelle_fille: str | None = Field(
        None, max_length=6, description="Section(2) + Numéro(4) de la parcelle fille"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id_dfi": "0000450",
                "code_departement": "023",
                "code_commune": "001",
                "prefixe": "000",
                "nature_dfi": "1",
                "date_validation": "1990-08-13",
                "numero_lot": "00001",
                "parcelle_mere": "AC0026",
                "parcelle_fille": "AC0214",
            }
        }


class FiliationNode(BaseModel):
    """Nœud d'arbre de filiation parcellaire.
    
    Représente une parcelle dans l'arbre généalogique administratif.
    Permet de remonter aux ancêtres (parcelles mères) de manière récursive.
    """

    id_parcelle: str = Field(description="Identifiant complet parcelle (Section + Numéro)")
    parent: Optional["FiliationNode"] = Field(
        None, description="Parcelle mère (ancêtre direct)"
    )
    children: list["FiliationNode"] = Field(
        default_factory=list, description="Parcelles filles (descendants directs)"
    )
    date_division: date | None = Field(
        None, description="Date de l'opération qui a créé cette parcelle"
    )
    nature_operation: DFINature | None = Field(
        None, description="Type d'opération (division, lotissement, etc.)"
    )
    depth: int = Field(default=0, ge=0, description="Profondeur dans l'arbre (0 = racine)")

    class Config:
        # Allow self-referential models
        json_schema_extra = {
            "example": {
                "id_parcelle": "AC0214",
                "parent": {
                    "id_parcelle": "AC0026",
                    "parent": None,
                    "children": [],
                    "date_division": None,
                    "nature_operation": None,
                    "depth": 1,
                },
                "children": [],
                "date_division": "1990-08-13",
                "nature_operation": "1",
                "depth": 0,
            }
        }


# Enable forward references for self-referential models
FiliationNode.model_rebuild()
