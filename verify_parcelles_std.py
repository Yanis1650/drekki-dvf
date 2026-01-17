
import json
import urllib.request


def test_parcelles():
    # Toulouse Center BBOX (small area)
    bbox = "1.440,43.600,1.450,43.610"
    url = f"http://localhost:8000/api/v1/transactions/parcelles?bbox={bbox}"
    try:
        with urllib.request.urlopen(url) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                print(f"SUCCESS: Got {len(data['features'])} features.")
                if len(data['features']) > 0:
                     print("Sample Prop:", data['features'][0]['properties'])
    except urllib.error.HTTPError as e:
        print(f"HTTP ERROR: {e.code}")
        print(e.read().decode())
    except Exception as e:
        print(f"EXCEPTION: {e}")

if __name__ == "__main__":
    test_parcelles()
