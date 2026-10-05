"""Emprise rectangulaire de pre-filtrage, partagee par les requetes POI.

Un rectangle n'est pas un disque : son coin est a racine de deux fois le
rayon. L'emprise ne sert donc qu'a reduire le nombre de lignes avant le
calcul Haversine ; c'est a l'appelant de borner la distance reelle s'il y
tient. `get_poi_in_radius` le fait, `get_nearest_poi` non — ecart epingle
par `tests/test_poi_repository.py`.
"""

from math import cos, radians

# Longueur d'un degre de latitude, en metres.
DEGRE_LATITUDE_M = 111000


def emprise(lat: float, lon: float, rayon_m: float) -> list[float]:
    """Rend [lon_min, lon_max, lat_min, lat_max] autour d'un point."""
    lat_delta = rayon_m / DEGRE_LATITUDE_M
    lon_delta = rayon_m / (DEGRE_LATITUDE_M * abs(cos(radians(lat))))
    return [
        lon - lon_delta, lon + lon_delta,
        lat - lat_delta, lat + lat_delta,
    ]
