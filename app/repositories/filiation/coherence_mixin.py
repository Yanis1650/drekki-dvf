"""Validation geometrique fille/mere, facultative par construction.

Geometries en Lambert-93 (EPSG:2154) dans la table `parcelles`. Le calcul
repose sur l'extension DuckDB Spatial ; son absence rend simplement le verdict
« NON_VERIFIABLE » plutot que d'echouer.
"""

import logging

logger = logging.getLogger(__name__)


class FiliationCoherenceMixin:
    """Recouvrement geometrique entre une parcelle mere et sa fille."""

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
