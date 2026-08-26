"""Filiation repository interfaces and implementations.

Provides access to parcel filiation data stored in DuckDB.

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
from abc import ABC, abstractmethod
from pathlib import Path

import duckdb

from app.domain.filiation_models import FiliationNode, ParcelFiliation

logger = logging.getLogger(__name__)

# Profondeur max par défaut pour la reconstruction d'arbre.
# Les communes avec remembrements successifs peuvent dépasser 10 niveaux ;
# la troncature évite les timeouts et les récursions infinies sur cycles DFI.
DEFAULT_DEPTH_LIMIT = 10


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

    @abstractmethod
    def build_filiation_tree(
        self,
        code_commune: str,
        section: str,
        numero: str,
        depth_limit: int = DEFAULT_DEPTH_LIMIT,
        _depth: int = 0,
        _visited: set[str] | None = None,
    ) -> FiliationNode:
        """Reconstruct the ancestor tree with depth bounding and cycle detection.

        Args:
            code_commune: 3-digit commune code
            section: 2-char section
            numero: 4-char parcel number
            depth_limit: Maximum recursion depth before truncation (default 10)
            _depth: Current depth (internal — do not pass from outside)
            _visited: Set of already-visited parcelle IDs (internal — cycle detection)

        Returns:
            FiliationNode with parent chain, possibly truncated.
        """

    @abstractmethod
    def calculate_coherence_geo(
        self,
        id_mere: str,
        id_fille: str,
    ) -> str:
        """Compute geometric coherence between a mother and daughter parcel.

        Uses ST_Intersection to compute area_overlap_pct =
          ST_Area(ST_Intersection(mere, fille)) / ST_Area(fille)

        Returns:
            'OK'             if overlap_pct >= 0.80
            'PARTIELLE'      if overlap_pct >= 0.30
            'DOUTEUSE'       if overlap_pct <  0.30  (WARNING logged)
            'NON_VERIFIABLE' if geometries not available or query fails
        """


class DuckDBFiliationRepository(IFiliationRepository):
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
            self._conn = duckdb.connect(str(self._db_path), read_only=True)
        return self._conn

    # ------------------------------------------------------------------
    # Raw data access
    # ------------------------------------------------------------------

    def get_parents(
        self, code_commune: str, section: str, numero: str
    ) -> list[ParcelFiliation]:
        """Retrieve parent parcels using optimized index scan.

        Query uses idx_dfi_fille index for fast lookup.
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
            logger.error("Error fetching parents for %s%s: %s", section, numero, e)
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
            logger.error("Error fetching children for %s%s: %s", section, numero, e)
            return []

    # ------------------------------------------------------------------
    # Tree reconstruction — depth-bounded + cycle-safe
    # ------------------------------------------------------------------

    def build_filiation_tree(
        self,
        code_commune: str,
        section: str,
        numero: str,
        depth_limit: int = DEFAULT_DEPTH_LIMIT,
        _depth: int = 0,
        _visited: set[str] | None = None,
    ) -> FiliationNode:
        """Reconstruct the ancestor tree with depth bounding and cycle detection.

        Algorithm:
          1. Vérifier si parcelle_key est déjà dans _visited → cycle → arrêt + ERROR
          2. Vérifier _depth >= depth_limit → troncature → arrêt + WARNING
          3. Récupérer les parents depuis DFI
          4. Récursion sur le premier parent (cas simple) avec _visited mis à jour
          5. Calcul optionnel de cohérence géométrique fille/mère

        Note : les remembrements (SAFER) ne figurent pas dans les DFI ;
        un arbre sans ancêtre connu peut être normal pour ces communes.
        """
        if _visited is None:
            _visited = set()

        parcelle_key = f"{section}{numero.zfill(4)}"

        # --- Cycle detection -----------------------------------------------
        if parcelle_key in _visited:
            logger.error(
                "Cycle détecté dans filiation : %s est déjà dans la chaîne ancêtre "
                "(commune=%s). Arbre partiel retourné.",
                parcelle_key,
                code_commune,
            )
            return FiliationNode(
                id_parcelle=parcelle_key,
                depth=_depth,
                truncated=True,
                coherence_geo="NON_VERIFIABLE",
            )

        # --- Depth limit -------------------------------------------------------
        if _depth >= depth_limit:
            logger.warning(
                "Arbre filiation tronqué à depth=%d pour parcelle %s (commune=%s)",
                depth_limit,
                parcelle_key,
                code_commune,
            )
            return FiliationNode(
                id_parcelle=parcelle_key,
                depth=_depth,
                truncated=True,
                coherence_geo="NON_VERIFIABLE",
            )

        # Mark current node as visited before recursing
        _visited.add(parcelle_key)

        # --- Query parents -----------------------------------------------------
        parents = self.get_parents(code_commune, section, numero)

        if not parents:
            # Leaf node — original parcel, no known division
            return FiliationNode(
                id_parcelle=parcelle_key,
                depth=_depth,
            )

        # Take first parent (most common case: simple division)
        # TODO: Handle multiple parents (fusion) in future version
        parent_filiation = parents[0]
        parent_section = parent_filiation.parcelle_mere[:2]
        parent_numero = parent_filiation.parcelle_mere[2:]

        # --- Optional geometry coherence ---------------------------------------
        # Build full 14-char parcel IDs for the geometry check.
        # dept_prefix: last 2 chars of code_departement
        # ("035" → "35", "2A" → "2A", "971" → "71")
        dept = parent_filiation.code_departement[-2:] if parent_filiation.code_departement else ""
        prefixe = parent_filiation.prefixe or "000"
        id_fille = dept + parent_filiation.code_commune + prefixe + section + numero.zfill(4)
        id_mere = dept + parent_filiation.code_commune + prefixe + parent_section + parent_numero

        coherence = self.calculate_coherence_geo(id_mere, id_fille)

        # --- Recurse on parent -------------------------------------------------
        parent_node = self.build_filiation_tree(
            code_commune,
            parent_section,
            parent_numero,
            depth_limit=depth_limit,
            _depth=_depth + 1,
            _visited=_visited,
        )

        return FiliationNode(
            id_parcelle=parcelle_key,
            parent=parent_node,
            date_division=parent_filiation.date_validation,
            nature_operation=parent_filiation.nature_dfi,
            depth=_depth,
            coherence_geo=coherence,
        )

    # ------------------------------------------------------------------
    # Geometry coherence validation
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_overlap(overlap_pct: float | None) -> str:
        """Classify a geometry overlap percentage as a coherence label.

        Pure function — no I/O, testable without DB.

        Args:
            overlap_pct: ST_Area(intersection) / ST_Area(fille), in [0, 1] or None

        Returns:
            'OK'             if overlap_pct >= 0.80
            'PARTIELLE'      if overlap_pct >= 0.30
            'DOUTEUSE'       if overlap_pct <  0.30
            'NON_VERIFIABLE' if overlap_pct is None
        """
        if overlap_pct is None:
            return "NON_VERIFIABLE"
        if overlap_pct >= 0.80:
            return "OK"
        if overlap_pct >= 0.30:
            return "PARTIELLE"
        return "DOUTEUSE"

    def calculate_coherence_geo(
        self,
        id_mere: str,
        id_fille: str,
    ) -> str:
        """Compute geometric coherence between a mother and daughter parcel.

        Queries the `parcelles` table (Lambert-93 geometries) and computes:
          overlap_pct = ST_Area(ST_Intersection(mere, fille)) / ST_Area(fille)

        This validation is OPTIONAL: returns 'NON_VERIFIABLE' if:
          - Either parcel is not found in the `parcelles` table
          - The spatial extension is not loaded
          - Any other query error

        A WARNING is logged when coherence is 'DOUTEUSE' (overlap < 30%).
        """
        if not id_mere or not id_fille or len(id_mere) != 14 or len(id_fille) != 14:
            return "NON_VERIFIABLE"

        try:
            conn = self._get_connection()
            result = conn.execute(
                """
                SELECT
                    CASE
                        WHEN ST_Area(f.geometry) > 0
                            THEN ST_Area(ST_Intersection(m.geometry, f.geometry))
                                 / ST_Area(f.geometry)
                        ELSE NULL
                    END AS overlap_pct
                FROM parcelles m
                JOIN parcelles f ON true
                WHERE m.id_parcelle = ?
                  AND f.id_parcelle = ?
                """,
                [id_mere, id_fille],
            ).fetchone()

            overlap_pct = float(result[0]) if result and result[0] is not None else None

        except Exception as e:
            logger.debug(
                "Geometry validation skipped for mere=%s fille=%s : %s",
                id_mere,
                id_fille,
                e,
            )
            return "NON_VERIFIABLE"

        label = self._classify_overlap(overlap_pct)

        if label == "DOUTEUSE":
            logger.warning(
                "Cohérence géométrique DOUTEUSE : mere=%s fille=%s (overlap=%.1f%%)",
                id_mere,
                id_fille,
                (overlap_pct or 0) * 100,
            )

        return label

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
