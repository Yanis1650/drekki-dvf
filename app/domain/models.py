"""Domain models for Foncier-Express.

Pure Pydantic V2 models with no external dependencies.
SRID: Lambert-93 (EPSG:2154) for internal storage.
"""

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, computed_field


class NatureMutation(str, Enum):
    """Types de mutations DVF."""

    VENTE = "Vente"
    VENTE_ETAT_FUTUR = "Vente en l'état futur d'achèvement"
    ADJUDICATION = "Adjudication"
    ECHANGE = "Echange"
    EXPROPRIATION = "Expropriation"


class TypeLocal(str, Enum):
    """Types de locaux DVF (Type 1 & 2 pour calcul prix/m²)."""

    MAISON = "Maison"
    APPARTEMENT = "Appartement"
    DEPENDANCE = "Dépendance"
    LOCAL_INDUSTRIEL = "Local industriel. commercial ou assimilé"


# --- Annotated Types (Pydantic V2) ---
CodeCommune = Annotated[str, Field(min_length=5, max_length=5, pattern=r"^\d{5}$")]
CodeParcelle = Annotated[str, Field(min_length=14, max_length=14)]
SurfaceM2 = Annotated[Decimal, Field(gt=0)]


class Parcelle(BaseModel):
    """Entité parcelle cadastrale."""

    id_parcelle: CodeParcelle
    code_commune: CodeCommune
    prefixe: str = Field(max_length=3)
    section: str = Field(max_length=2)
    numero: str = Field(max_length=4)
    geometry_wkt: str | None = None
    surface_m2: SurfaceM2 | None = None

    @computed_field
    @property
    def code_section(self) -> str:
        """Code section complet (commune + prefixe + section)."""
        return f"{self.code_commune}{self.prefixe}{self.section}"


class Transaction(BaseModel):
    """Transaction DVF individuelle."""

    id_mutation: str
    date_mutation: date
    nature_mutation: NatureMutation
    valeur_fonciere: Decimal = Field(ge=0)
    code_commune: CodeCommune
    id_parcelle: CodeParcelle
    type_local: TypeLocal | None = None
    surface_reelle_bati: SurfaceM2 | None = None
    nombre_pieces: int | None = Field(default=None, ge=0)


class MutationAggregate(BaseModel):
    """Mutation agrégée par id_mutation (méthodologie Mericskay).

    Regroupe toutes les lignes DVF partageant le même id_mutation
    pour traiter la cardinalité 1-N (Maison + Dépendances).
    """

    id_mutation: str
    date_mutation: date
    nature_mutation: NatureMutation
    valeur_fonciere: Decimal
    code_commune: str  # Relaxed validation for ETL compatibility
    parcelles: list[str]  # Relaxed validation for ETL compatibility
    surface_habitable_totale: Decimal
    nombre_locaux: int = Field(ge=1)
    type_local: TypeLocal | None = None
    longitude: float | None = None
    latitude: float | None = None
    is_outlier: bool = False  # Prix/m² hors P5-P95 communal ou départemental

    @computed_field
    @property
    def prix_m2(self) -> Decimal | None:
        """Prix au m² calculé selon Mericskay (valeur / surface habitable)."""
        if self.surface_habitable_totale > 0:
            return self.valeur_fonciere / self.surface_habitable_totale
        return None


class EnrichmentScore(BaseModel):
    """Score d'enrichissement qualitatif pour une parcelle.

    Agrège les données contextuelles (écoles, transports, nuisances).
    transit_score est calculé à la volée (gaussienne TOD) — pas stocké en base.
    """

    id_parcelle: CodeParcelle
    schools_score: Decimal = Field(ge=0, le=10, default=Decimal("5.0"))
    transport_score: Decimal = Field(ge=0, le=10, default=Decimal("5.0"))
    transit_score: Decimal = Field(ge=0, le=10, default=Decimal("5.0"))
    nuisances_score: Decimal = Field(ge=0, le=10, default=Decimal("5.0"))
    green_spaces_score: Decimal = Field(ge=0, le=10, default=Decimal("5.0"))
    commerce_score: Decimal = Field(ge=0, le=10, default=Decimal("5.0"))

    @computed_field
    @property
    def global_score(self) -> Decimal:
        """Score global pondéré sur 6 composantes.

        Pondérations :
          schools_score    20%
          transport_score  15%  (bus, vélo)
          transit_score    20%  (gares — courbe cloche TOD)
          nuisances_score  20%  (inversé)
          green_spaces     10%
          commerce_score   15%
        """
        weighted = (
            self.schools_score     * Decimal("0.20")
            + self.transport_score * Decimal("0.15")
            + self.transit_score   * Decimal("0.20")
            + self.nuisances_score * Decimal("0.20")
            + self.green_spaces_score * Decimal("0.10")
            + self.commerce_score  * Decimal("0.15")
        )
        return weighted.quantize(Decimal("0.01"))


class DensificationScore(BaseModel):
    """Score de potentiel de densification pour une parcelle (ZAN).

    Calcule le CES (Coefficient d'Emprise au Sol) actuel et le compare
    au CES potentiel (PLU ou défaut 40%) pour identifier les "dents creuses".
    """

    id_parcelle: CodeParcelle
    surface_parcelle_m2: Decimal = Field(gt=0)
    surface_plancher_m2: Decimal = Field(ge=0)
    ces_actuel: Decimal = Field(ge=0, le=1)  # 0.0 à 1.0 (0-100%)
    ces_potentiel: Decimal = Field(ge=0, le=1, default=Decimal("0.40"))  # Défaut 40%

    @computed_field
    @property
    def potentiel_densification(self) -> Decimal:
        """Potentiel de densification en ratio (0.0 à 1.0).

        Exemple: CES actuel 10%, potentiel 40% → 0.30 (30% de marge)
        """
        return max(Decimal("0"), self.ces_potentiel - self.ces_actuel)

    @computed_field
    @property
    def surface_constructible_restante(self) -> Decimal:
        """Surface constructible restante en m².

        Calcul: potentiel_densification × surface_parcelle
        """
        return self.potentiel_densification * self.surface_parcelle_m2

    @computed_field
    @property
    def categorie(self) -> str:
        """Catégorie de potentiel : FORT / MOYEN / FAIBLE / SATURE.

        - FORT: potentiel ≥ 20%
        - MOYEN: potentiel ≥ 10%
        - FAIBLE: potentiel > 0%
        - SATURE: potentiel = 0%
        """
        if self.potentiel_densification >= Decimal("0.20"):
            return "FORT"
        elif self.potentiel_densification >= Decimal("0.10"):
            return "MOYEN"
        elif self.potentiel_densification > Decimal("0"):
            return "FAIBLE"
        else:
            return "SATURE"
