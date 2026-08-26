"""Mixin pour les opérations parcelle et GeoJSON."""

import logging
from decimal import Decimal

from app.domain.models import Parcelle
from app.repositories.duckdb_geojson import build_parcelles_geojson, build_transactions_geojson

logger = logging.getLogger(__name__)


class DuckDBParcellesMixin:
    """Mixin parcelle, GeoJSON et bbox."""

    async def get_parcelle_by_id(self, id_parcelle: str) -> Parcelle | None:
        """Retrieve a single parcel by its ID."""
        conn = self._get_connection(self._dept_from_parcelle(id_parcelle))
        result = conn.execute(
            """
            SELECT id_parcelle, code_commune, prefixe, section, numero,
                   ST_AsText(geometry) as geometry_wkt
            FROM parcelles
            WHERE id_parcelle = ?
            """,
            [id_parcelle],
        ).fetchone()

        if result is None:
            return None

        return Parcelle(
            id_parcelle=result[0],
            code_commune=result[1],
            prefixe=result[2],
            section=result[3],
            numero=result[4],
            geometry_wkt=result[5],
            surface_m2=None,
        )

    async def get_parcelles_by_commune(self, code_commune: str) -> list[Parcelle]:
        """Retrieve all parcels in a commune."""
        conn = self._get_connection(self._dept_from_commune(code_commune))
        results = conn.execute(
            """
            SELECT id_parcelle, code_commune, prefixe, section, numero,
                   ST_AsText(geometry) as geometry_wkt, surface_m2
            FROM parcelles
            WHERE code_commune = ?
            """,
            [code_commune],
        ).fetchall()

        return [
            Parcelle(
                id_parcelle=r[0],
                code_commune=r[1],
                prefixe=r[2],
                section=r[3],
                numero=r[4],
                geometry_wkt=r[5],
                surface_m2=Decimal(str(r[6])) if r[6] else None,
            )
            for r in results
        ]

    async def get_transactions_geojson(
        self,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
        limit: int = 1000,
    ) -> str:
        """Retrieve DVF transactions as GeoJSON Point features."""
        conn = self._get_connection()
        return build_transactions_geojson(conn, min_x, min_y, max_x, max_y, limit)

    async def get_parcelles_geojson(
        self,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
        limit: int = 500,
        filter: str | None = None,
    ) -> str:
        """Retrieve cadastral parcels as GeoJSON Polygon features with transaction counts.
        filter: 'zan' (Fort potentiel ZAN) or 'recent' (Ventes < 2 ans).
        """
        conn = self._get_connection()
        return build_parcelles_geojson(
            conn, min_x, min_y, max_x, max_y, limit, filter,
            dept_prefix=getattr(self, "_dept_prefix", None),
        )

    async def get_parcelles_in_bbox(
        self,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
        limit: int = 1000,
    ) -> str:
        """DEPRECATED: Use get_parcelles_geojson() instead."""
        logger.warning("get_parcelles_in_bbox is deprecated. Use get_parcelles_geojson() instead.")
        return await self.get_parcelles_geojson(min_x, min_y, max_x, max_y, limit)
