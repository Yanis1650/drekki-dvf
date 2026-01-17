"""Script de test pour l'API GPU (Géoportail de l'Urbanisme).

Teste la récupération des zones PLU pour des coordonnées réelles.
"""

import asyncio

from app.services.plu_service import PLUService


async def test_gpu_api():
    """Test de l'API GPU avec des coordonnées réelles."""

    plu_service = PLUService()

    print("=" * 60)
    print("Test API GPU - Géoportail de l'Urbanisme")
    print("=" * 60)
    print()

    # Test 1: Rennes centre (zone urbaine attendue)
    print("Test 1: Rennes centre (Place de la Mairie)")
    print("-" * 60)
    code_commune = "35238"
    lon, lat = -1.6777, 48.1119

    try:
        zone = await plu_service.get_zone_plu(code_commune, lon, lat)
        ces = await plu_service.get_ces_potentiel(code_commune, lon, lat)

        print(f"  Coordonnées: {lon}, {lat}")
        print(f"  Zone PLU: {zone if zone else 'Non trouvée'}")
        print(f"  CES potentiel: {float(ces) * 100:.1f}%")
        print("  ✓ Test réussi")
    except Exception as e:
        print(f"  ✗ Erreur: {e}")

    print()

    # Test 2: Périphérie de Rennes (zone à urbaniser attendue)
    print("Test 2: Périphérie de Rennes")
    print("-" * 60)
    lon, lat = -1.6500, 48.1300

    try:
        zone = await plu_service.get_zone_plu(code_commune, lon, lat)
        ces = await plu_service.get_ces_potentiel(code_commune, lon, lat)

        print(f"  Coordonnées: {lon}, {lat}")
        print(f"  Zone PLU: {zone if zone else 'Non trouvée'}")
        print(f"  CES potentiel: {float(ces) * 100:.1f}%")
        print("  ✓ Test réussi")
    except Exception as e:
        print(f"  ✗ Erreur: {e}")

    print()

    # Test 3: Zone rurale (zone agricole/naturelle attendue)
    print("Test 3: Zone rurale autour de Rennes")
    print("-" * 60)
    lon, lat = -1.7500, 48.1500

    try:
        zone = await plu_service.get_zone_plu(code_commune, lon, lat)
        ces = await plu_service.get_ces_potentiel(code_commune, lon, lat)

        print(f"  Coordonnées: {lon}, {lat}")
        print(f"  Zone PLU: {zone if zone else 'Non trouvée'}")
        print(f"  CES potentiel: {float(ces) * 100:.1f}%")
        print("  ✓ Test réussi")
    except Exception as e:
        print(f"  ✗ Erreur: {e}")

    print()
    print("=" * 60)
    print("Tests terminés")
    print("=" * 60)

    await plu_service.close()


if __name__ == "__main__":
    asyncio.run(test_gpu_api())
