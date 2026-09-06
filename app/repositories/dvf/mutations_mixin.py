"""Mixin des mutations agregees : par commune et par rayon geodesique."""

from datetime import date
from math import cos, radians

from app.domain.models import MutationAggregate
from app.repositories.dvf.mapping import (
    COLONNES_MUTATION,
    appliquer_bornes,
    vers_mutations,
)

# Rayon terrestre moyen et longueur d'un degre de latitude, en metres.
RAYON_TERRE_M = 6371000
DEGRE_LATITUDE_M = 111000


class DvfMutationsMixin:
    """Lectures de la table `mutations_aggregated`."""

    async def get_mutations_by_commune(
        self,
        code_commune: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[MutationAggregate]:
        """Retrieve aggregated mutations (pre-computed by ETL)."""
        conn = self._get_connection()
        query = f"""
            SELECT {COLONNES_MUTATION}
            FROM mutations_aggregated
            WHERE code_commune = ?
        """
        params: list = [code_commune]
        query = appliquer_bornes(query, params, date_from, date_to)

        return vers_mutations(conn.execute(query, params).fetchall())

    async def get_mutations_in_radius(
        self,
        lat: float,
        lon: float,
        radius_meters: int,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 100,
    ) -> list[MutationAggregate]:
        """Retrieve mutations within a radius using Haversine.

        Une emprise rectangulaire pre-filtre les lignes avant le calcul de
        distance, qui est le poste couteux.
        """
        conn = self._get_connection()

        lat_delta = radius_meters / DEGRE_LATITUDE_M
        lon_delta = radius_meters / (DEGRE_LATITUDE_M * abs(cos(radians(lat))))

        query = f"""
            WITH bbox_filtered AS (
                SELECT *
                FROM mutations_aggregated
                WHERE longitude IS NOT NULL
                  AND latitude IS NOT NULL
                  AND longitude BETWEEN ? AND ?
                  AND latitude BETWEEN ? AND ?
            ),
            with_distance AS (
                SELECT *,
                    {RAYON_TERRE_M} * ACOS(
                        LEAST(1.0, GREATEST(-1.0,
                            COS(RADIANS(?)) * COS(RADIANS(latitude)) *
                            COS(RADIANS(longitude) - RADIANS(?)) +
                            SIN(RADIANS(?)) * SIN(RADIANS(latitude))
                        ))
                    ) AS distance_meters
                FROM bbox_filtered
            )
            SELECT {COLONNES_MUTATION}, prix_m2, longitude, latitude, distance_meters
            FROM with_distance
            WHERE distance_meters <= ?
        """
        params: list = [
            lon - lon_delta, lon + lon_delta,
            lat - lat_delta, lat + lat_delta,
            lat, lon, lat,
            radius_meters,
        ]
        query = appliquer_bornes(query, params, date_from, date_to)

        query += " ORDER BY distance_meters ASC LIMIT ?"
        params.append(limit)

        resultats = conn.execute(query, params).fetchall()
        return vers_mutations(resultats, avec_coordonnees=True)
