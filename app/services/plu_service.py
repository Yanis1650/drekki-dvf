"""Intégration PLU - Récupération CES potentiel par zone.

Ce module permet de récupérer les données PLU (Plan Local d'Urbanisme)
depuis le Géoportail de l'Urbanisme (GPU) pour moduler le CES potentiel
selon la zone (U/AU/A/N).

API GPU: https://www.geoportail-urbanisme.gouv.fr/
"""

from decimal import Decimal

import httpx

# Mapping zone PLU → CES potentiel
CES_BY_ZONE = {
    "U": Decimal("0.50"),    # Zone urbaine: 50%
    "AU": Decimal("0.30"),   # Zone à urbaniser: 30%
    "A": Decimal("0.05"),    # Zone agricole: 5%
    "N": Decimal("0.02"),    # Zone naturelle: 2%
    "DEFAULT": Decimal("0.40"),  # Défaut si zone inconnue
}


class PLUService:
    """Service pour récupérer les données PLU depuis le GPU."""

    def __init__(self, api_base_url: str = "https://www.geoportail-urbanisme.gouv.fr/api"):
        self.api_base_url = api_base_url
        self.client = httpx.AsyncClient(timeout=10.0)

    async def get_zone_plu(self, code_commune: str, longitude: float, latitude: float) -> str | None:
        """Récupère la zone PLU pour une coordonnée donnée.

        Args:
            code_commune: Code INSEE de la commune (5 caractères)
            longitude: Longitude WGS84
            latitude: Latitude WGS84

        Returns:
            Code zone PLU (U/AU/A/N) ou None si non trouvé
        """
        try:
            # Endpoint GPU pour interrogation par point
            url = f"{self.api_base_url}/document/{code_commune}/zone"
            params = {
                "lon": longitude,
                "lat": latitude,
                "format": "json"
            }

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            # Extraire le code zone (format: "U", "AU", "A", "N", etc.)
            if "features" in data and len(data["features"]) > 0:
                zone_code = data["features"][0]["properties"].get("libelle", "")

                # Normaliser (prendre premier caractère)
                if zone_code:
                    return zone_code[0].upper()

            return None

        except httpx.HTTPError as e:
            print(f"Erreur API GPU: {e}")
            return None
        except Exception as e:
            print(f"Erreur inattendue: {e}")
            return None

    async def get_ces_potentiel(self, code_commune: str, longitude: float, latitude: float) -> Decimal:
        """Récupère le CES potentiel pour une parcelle selon sa zone PLU.

        Args:
            code_commune: Code INSEE de la commune
            longitude: Longitude WGS84
            latitude: Latitude WGS84

        Returns:
            CES potentiel (Decimal entre 0.0 et 1.0)
        """
        zone = await self.get_zone_plu(code_commune, longitude, latitude)

        if zone and zone in CES_BY_ZONE:
            return CES_BY_ZONE[zone]

        # Fallback sur valeur par défaut
        return CES_BY_ZONE["DEFAULT"]

    async def close(self):
        """Ferme le client HTTP."""
        await self.client.aclose()


# Fonction helper pour mise à jour batch
async def update_ces_potentiel_from_plu(parcelles: list[dict]) -> dict[str, Decimal]:
    """Met à jour le CES potentiel pour une liste de parcelles via PLU.

    Args:
        parcelles: Liste de dicts avec keys: id_parcelle, code_commune, longitude, latitude

    Returns:
        Dict mapping id_parcelle → ces_potentiel
    """
    plu_service = PLUService()
    results = {}

    try:
        for parcelle in parcelles:
            ces = await plu_service.get_ces_potentiel(
                code_commune=parcelle["code_commune"],
                longitude=parcelle["longitude"],
                latitude=parcelle["latitude"]
            )
            results[parcelle["id_parcelle"]] = ces
    finally:
        await plu_service.close()

    return results


# TODO: Intégrer dans ETL densification
# Exemple d'utilisation dans etl_densification.py:
#
# from app.services.plu_service import update_ces_potentiel_from_plu
#
# # Après création de parcelles_bdnb, avant calcul CES:
# parcelles_list = conn.execute("""
#     SELECT id_parcelle, code_commune,
#            ST_X(ST_Centroid(geometry)) as longitude,
#            ST_Y(ST_Centroid(geometry)) as latitude
#     FROM parcelles
#     WHERE code_commune LIKE '35%'
#     LIMIT 1000  -- Batch processing
# """).fetchall()
#
# ces_potentiel_map = await update_ces_potentiel_from_plu(parcelles_list)
#
# # Utiliser ces_potentiel_map dans la requête SQL
