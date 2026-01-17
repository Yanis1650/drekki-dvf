"""Verify that parcelles geometries are now in WGS84"""

import requests

bbox_rennes = "-1.68,48.11,-1.67,48.12"
url = f"http://localhost:8000/api/v1/land/parcelles?bbox={bbox_rennes}"

print("Testing parcelles geometry projection...")
print(f"URL: {url}\n")

try:
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        count = len(data.get('features', []))
        print("✅ Status: 200 OK")
        print(f"✅ Features: {count} parcelles\n")

        if count > 0:
            # Check first parcel coordinates
            first_parcel = data['features'][0]
            coords = first_parcel['geometry']['coordinates']

            print(f"Sample parcel: {first_parcel['properties']['id_parcelle']}")
            print(f"Geometry type: {first_parcel['geometry']['type']}")

            # Get first coordinate pair
            if first_parcel['geometry']['type'] == 'Polygon':
                first_coord = coords[0][0]  # First ring, first point
            elif first_parcel['geometry']['type'] == 'MultiPolygon':
                first_coord = coords[0][0][0]  # First polygon, first ring, first point
            else:
                first_coord = coords[0]

            print(f"First coordinate: {first_coord}")

            # Check if coordinates are in WGS84 range
            lon, lat = first_coord[0], first_coord[1]

            if -180 <= lon <= 180 and -90 <= lat <= 90:
                print("\n✅ COORDINATES ARE IN WGS84!")
                print(f"   Longitude: {lon:.6f}° (valid range: -180 to 180)")
                print(f"   Latitude: {lat:.6f}° (valid range: -90 to 90)")

                # Check if in Rennes area
                if -2 < lon < -1 and 48 < lat < 49:
                    print("   ✅ Coordinates are in Rennes area!")
                else:
                    print("   ⚠️  Coordinates outside Rennes area")
            else:
                print("\n❌ COORDINATES ARE NOT IN WGS84!")
                print(f"   Longitude: {lon} (expected: -2 to -1 for Rennes)")
                print(f"   Latitude: {lat} (expected: 48 to 49 for Rennes)")
                print("   These look like Lambert-93 coordinates!")
        else:
            print("⚠️  No parcelles returned")
    else:
        print(f"❌ Status: {response.status_code}")
        print(f"Error: {response.text}")

except Exception as e:
    print(f"❌ Request failed: {e}")
