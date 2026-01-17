"""Test parcelles endpoint with Rennes bbox (dept 35)"""
import json
import urllib.request

# Rennes center: -1.6778, 48.1173
# Bbox around Rennes center
bbox = "-1.68,48.11,-1.67,48.12"
url = f"http://127.0.0.1:8000/api/v1/transactions/parcelles?bbox={bbox}"

print(f"Testing: {url}")
try:
    with urllib.request.urlopen(url, timeout=30) as response:
        data = json.loads(response.read().decode())
        print(f"SUCCESS: Got {len(data['features'])} features.")
        if len(data['features']) > 0:
            print("\nSample properties:")
            for i, f in enumerate(data['features'][:5]):
                props = f.get('properties', {})
                print(f"  {i+1}. id={props.get('id', 'N/A')[:20]}... dpe={props.get('dpe', 'N/A')} annee={props.get('annee', 'N/A')}")
except Exception as e:
    print(f"ERROR: {e}")
