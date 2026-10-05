"""Implementation DuckDB du depot de filiation cadastrale.

Le contrat `IFiliationRepository` vit avec les autres interfaces de depot,
dans `interfaces/` : ce fichier ne porte plus que son implementation.

Provides access to parcel filiation data stored in DuckDB.

Les trois familles de lecture vivent dans `app/repositories/filiation/` :
acces brut aux liens DFI, reconstruction de l'arbre, validation geometrique.
Ce module garde la connexion et la garde sur la disponibilite des donnees.

Limite documentée — aménagements fonciers ruraux (remembrements) :
  Les opérations de remembrement (SAFER, aménagement foncier agricole)
  ne sont PAS couvertes par les DFI. Ces opérations regroupent ou
  redistribuent des parcelles sans correspondance géographique 1-à-1 ;
  la filiation DFI n'est donc pas applicable. Les communes concernées
  peuvent présenter des arbres incomplets (pas d'ancêtre retrouvé) même
  pour des parcelles récentes — ce n'est pas un bug de l'implémentation.
  Référence : data.gouv.fr/fr/datasets/historique-des-parcelles-cadastrales-filiation/
"""

import logging
from pathlib import Path

import duckdb

from app.infrastructure.data_availability import require_table
from app.infrastructure.duckdb_pool import close_shared_connection, get_shared_connection
from app.repositories.filiation import (
    FiliationCoherenceMixin,
    FiliationLineageMixin,
    FiliationTreeMixin,
)
from app.repositories.interfaces import DEFAULT_DEPTH_LIMIT, IFiliationRepository

logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_DEPTH_LIMIT",
    "DuckDBFiliationRepository",
    "IFiliationRepository",
]


class DuckDBFiliationRepository(
    FiliationLineageMixin,
    FiliationTreeMixin,
    FiliationCoherenceMixin,
    IFiliationRepository,
):
    """DuckDB implementation of filiation repository.

    Uses composite indexes for fast lookups:
    - idx_dfi_fille: (code_commune, parcelle_fille) for finding parents
    - idx_dfi_mere:  (code_commune, parcelle_mere)  for finding children

    Géométries stockées en Lambert-93 (EPSG:2154) dans la table `parcelles`.
    La validation géométrique (ST_Intersection) utilise l'extension DuckDB Spatial.
    """

    def __init__(self, db_path: Path | str = "./data/foncier.duckdb") -> None:
        self._db_path = Path(db_path)
        self._conn: duckdb.DuckDBPyConnection | None = None

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """Lazy connection initialization."""
        if self._conn is None:
            self._conn = get_shared_connection(self._db_path)
        return self._conn

    def _require_dfi(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Refuse de répondre si la filiation DFI n'a jamais été chargée.

        Sans cette garde, l'absence de `dfi_filiations` était rattrapée plus bas
        par un `except` et l'API concluait « parcelle originelle » pour toutes
        les parcelles du département.
        """
        require_table(
            conn,
            table="dfi_filiations",
            dataset="filiation cadastrale (DFI)",
            hint="Lancer : python data-pipeline/etl_dfi.py --dept <XX>",
        )

    def close(self) -> None:
        """Relache la connexion partagee de ce fichier."""
        close_shared_connection(self._db_path)
        self._conn = None
