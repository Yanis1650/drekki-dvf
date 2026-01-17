"""Verify that parcelles now include transaction_count property"""

import requests

bbox_rennes = "-1.68,48.11,-1.67,48.12"
url = f"http://localhost:8000/api/v1/land/parcelles?bbox={bbox_rennes}"

print("Testing transaction_count property...")
print(f"URL: {url}\n")

try:
    response = requests.get(url, timeout=30)

    if response.status_code == 200:
        data = response.json()
        count = len(data.get('features', []))
        print("✅ Status: 200 OK")
        print(f"✅ Features: {count} parcelles\n")

        if count > 0:
            # Check first few parcels for transaction_count
            print("Sample parcels with transaction counts:")
            for i, parcel in enumerate(data['features'][:5], 1):
                props = parcel['properties']
                parcel_id = props.get('id_parcelle', 'N/A')
                tx_count = props.get('transaction_count', 'MISSING')
                print(f"  {i}. {parcel_id}: {tx_count} transactions")

            # Count how many parcels have transactions
            parcels_with_tx = sum(1 for p in data['features'] if p['properties'].get('transaction_count', 0) > 0)
            print("\n📊 Statistics:")
            print(f"   Total parcels: {count}")
            print(f"   Parcels with transactions: {parcels_with_tx}")
            print(f"   Parcels without transactions: {count - parcels_with_tx}")

            if parcels_with_tx > 0:
                print("\n✅ SUCCESS! Transaction counting is working!")
            else:
                print("\n⚠️  No parcels have transactions. This might be normal if no DVF points fall within these parcels.")
        else:
            print("⚠️  No parcelles returned")
    else:
        print(f"❌ Status: {response.status_code}")
        print(f"Error: {response.text}")

except Exception as e:
    print(f"❌ Request failed: {e}")
    import traceback
    traceback.print_exc()
