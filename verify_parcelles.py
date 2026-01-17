
import asyncio

import httpx


async def test_parcelles():
    # Toulouse Center BBOX (small area)
    bbox = "1.440,43.600,1.450,43.610"
    url = f"http://localhost:8000/api/v1/transactions/parcelles?bbox={bbox}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                print(f"SUCCESS: Got {len(data['features'])} parcels.")
                if len(data['features']) > 0:
                    print("Sample ID:", data['features'][0]['properties']['id'])
            else:
                print(f"ERROR: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"EXCEPTION: {e}")

if __name__ == "__main__":
    asyncio.run(test_parcelles())
