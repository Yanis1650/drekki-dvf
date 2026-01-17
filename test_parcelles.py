"""Quick diagnostic script to test parcelles API and check data availability."""
import requests

# Test 1: Check if parcelles API works with a small bbox around Rennes
bbox_rennes = "-1.68,48.11,-1.67,48.12"  # Small area in Rennes
url = f"http://localhost:8000/api/v1/land/parcelles?bbox={bbox_rennes}"

print(f"Testing parcelles API: {url}")
try:
    response = requests.get(url)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        feature_count = len(data.get('features', []))
        print(f"✅ Success! Found {feature_count} parcelles")

        if feature_count > 0:
            print(f"Sample parcel: {data['features'][0]['properties']}")
        else:
            print("⚠️  No parcelles found in this area. Possible reasons:")
            print("   1. No cadastral data loaded for Rennes (dept 35)")
            print("   2. Bbox coordinates might be incorrect")
            print("   3. Spatial query might be failing")
    else:
        print(f"❌ Error: {response.text}")

except Exception as e:
    print(f"❌ Request failed: {e}")

# Test 2: Check transactions API for comparison
print("\n" + "="*50)
print("Testing transactions API for comparison...")
url_transactions = f"http://localhost:8000/api/v1/land/geojson?bbox={bbox_rennes}"
try:
    response = requests.get(url_transactions)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        feature_count = len(data.get('features', []))
        print(f"✅ Found {feature_count} transactions")
except Exception as e:
    print(f"❌ Request failed: {e}")
