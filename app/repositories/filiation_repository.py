"""Filiation repository interfaces and implementations.

Provides access to parcel filiation data stored in DuckDB.
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path

import duckdb

from app.domain.filiation_models import ParcelFiliation

logger = logging.getLogger(__name__)


class IFiliationRepository(ABC):
    """Interface for parcel filiation data access."""

    @abstractmethod
    def get_parents(
        self, code_commune: str, section: str, numero: str
    ) -> list[ParcelFiliation]:
        """Retrieve direct parent parcels (mothers).
        
        Args:
            code_commune: 3-digit commune code (ex: "001")
            section: 2-char section (ex: "AC")
            numero: 4-char parcel number (ex: "0214")
            
        Returns:
            List of parent filiations (may be empty)
        """
        pass

    @abstractmethod
    def get_children(
        self, code_commune: str, section: str, numero: str
    ) -> list[ParcelFiliation]:
        """Retrieve direct children parcels (daughters).
        
        Args:
            code_commune: 3-digit commune code
            section: 2-char section
            numero: 4-char parcel number
            
        Returns:
            List of children filiations (may be empty)
        """
        pass


class DuckDBFiliationRepository(IFiliationRepository):
    """DuckDB implementation of filiation repository.
    
    Uses composite indexes for fast lookups:
    - idx_dfi_fille: (code_commune, parcelle_fille) for finding parents
    - idx_dfi_mere: (code_commune, parcelle_mere) for finding children
    """

    def __init__(self, db_path: Path | str = "./data/foncier.duckdb") -> None:
        self._db_path = Path(db_path)
        self._conn: duckdb.DuckDBPyConnection | None = None

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """Lazy connection initialization."""
        if self._conn is None:
            self._conn = duckdb.connect(str(self._db_path), read_only=True)
        return self._conn

    def get_parents(
        self, code_commune: str, section: str, numero: str
    ) -> list[ParcelFiliation]:
        """Retrieve parent parcels using optimized index scan.
        
        Query uses idx_dfi_fille index for fast lookup.
        """
        conn = self._get_connection()

        # Construct parcelle_id (section + numero)
        parcelle_id = section + numero.zfill(4)

        query = """
            SELECT 
                id_dfi,
                code_departement,
                code_commune,
                prefixe,
                nature_dfi,
                date_validation,
                numero_lot,
                parcelle_mere,
                parcelle_fille
            FROM dfi_filiations
            WHERE code_commune = ?
              AND parcelle_fille = ?
            ORDER BY date_validation DESC
        """

        try:
            results = conn.execute(query, [code_commune, parcelle_id]).fetchall()

            return [
                ParcelFiliation(
                    id_dfi=row[0],
                    code_departement=row[1],
                    code_commune=row[2],
                    prefixe=row[3],
                    nature_dfi=row[4],
                    date_validation=row[5],
                    numero_lot=row[6],
                    parcelle_mere=row[7],
                    parcelle_fille=row[8],
                )
                for row in results
            ]
        except Exception as e:
            logger.error(f"Error fetching parents for {section}{numero}: {e}")
            return []

    def get_children(
        self, code_commune: str, section: str, numero: str
    ) -> list[ParcelFiliation]:
        """Retrieve children parcels using optimized index scan.
        
        Query uses idx_dfi_mere index for fast lookup.
        """
        conn = self._get_connection()

        parcelle_id = section + numero.zfill(4)

        query = """
            SELECT 
                id_dfi,
                code_departement,
                code_commune,
                prefixe,
                nature_dfi,
                date_validation,
                numero_lot,
                parcelle_mere,
                parcelle_fille
            FROM dfi_filiations
            WHERE code_commune = ?
              AND parcelle_mere = ?
            ORDER BY date_validation DESC
        """

        try:
            results = conn.execute(query, [code_commune, parcelle_id]).fetchall()

            return [
                ParcelFiliation(
                    id_dfi=row[0],
                    code_departement=row[1],
                    code_commune=row[2],
                    prefixe=row[3],
                    nature_dfi=row[4],
                    date_validation=row[5],
                    numero_lot=row[6],
                    parcelle_mere=row[7],
                    parcelle_fille=row[8],
                )
                for row in results
            ]
        except Exception as e:
            logger.error(f"Error fetching children for {section}{numero}: {e}")
            return []

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
