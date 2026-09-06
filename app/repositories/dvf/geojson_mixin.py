"""Mixin GeoJSON : parcelles d'une emprise, servies a la carte."""

import json
import logging

logger = logging.getLogger(__name__)

# Demi-cote du carre dessine autour de chaque point, en degres (~5 m).
DEMI_COTE_DEG = 0.00005

_REQUETE_PARCELLES = """
    SELECT
        id_mutation as id,
        longitude,
        latitude,
        classe_consommation_energie as dpe,
        annee_construction as annee,
        valeur_fonciere,
        surface_reelle
    FROM france_foncier_test
    WHERE longitude IS NOT NULL
      AND latitude IS NOT NULL
      AND longitude BETWEEN ? AND ?
      AND latitude BETWEEN ? AND ?
    LIMIT ?
"""


def _carre(lon: float, lat: float) -> list[list[list[float]]]:
    """Anneau ferme approximant une emprise batie autour d'un point."""
    d = DEMI_COTE_DEG
    return [[
        [lon - d, lat - d],
        [lon + d, lat - d],
        [lon + d, lat + d],
        [lon - d, lat + d],
        [lon - d, lat - d],
    ]]


class DvfGeojsonMixin:
    """Rendu GeoJSON des parcelles enrichies."""

    async def get_parcelles_in_bbox(
        self,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
        limit: int = 1000,
    ) -> str:
        """Retrieve parcelles as GeoJSON FeatureCollection with DPE data.

        S'appuie sur `france_foncier_test`, qui porte les donnees enrichies
        (DPE, annee de construction). Faute de geometrie disponible, chaque
        mutation est rendue par un petit carre centre sur son point, suffisant
        pour la visualisation.
        """
        conn = self._get_connection()

        try:
            resultats = conn.execute(
                _REQUETE_PARCELLES, [min_x, max_x, min_y, max_y, limit]
            ).fetchall()
        except Exception as e:
            logger.warning(
                "Requete france_foncier_test echouee (%s) — collection vide", e
            )
            resultats = []

        features = []
        for r in resultats:
            identifiant, lon, lat, dpe, annee = r[0], r[1], r[2], r[3], r[4]
            if not lon or not lat:
                continue

            proprietes: dict = {"id": str(identifiant)}
            if dpe:
                proprietes["dpe"] = dpe
            if annee:
                proprietes["annee"] = int(annee)

            features.append({
                "type": "Feature",
                "properties": proprietes,
                "geometry": {"type": "Polygon", "coordinates": _carre(lon, lat)},
            })

        return json.dumps(
            {"type": "FeatureCollection", "features": features},
            ensure_ascii=False,
        )
