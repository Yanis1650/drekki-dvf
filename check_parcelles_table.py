"""Check parcelles table status in DuckDB"""
import requests

print("=" * 60)
print("Checking parcelles table status via backend...")
print("=" * 60)

# The backend is already running and has access to DuckDB
# We can check the debug logs when it connects

# Test 1: Try to fetch parcelles for a known area
bbox_rennes = "-1.68,48.11,-1.67,48.12"
url = f"http://localhost:8000/api/v1/land/parcelles?bbox={bbox_rennes}"

print(f"\n1. Testing parcelles API: {url}")
try:
    response = requests.get(url)
    print(f"   Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        count = len(data.get('features', []))
        print(f"   Features: {count}")

        if count == 0:
            print("\n⚠️  API works but returns 0 parcelles")
            print("   Possible causes:")
            print("   1. Table 'parcelles' is empty")
            print("   2. Table doesn't have dept 35 data")
            print("   3. Spatial query is failing")
    else:
        error = response.json()
        print(f"   Error: {error}")

except Exception as e:
    print(f"   ❌ Request failed: {e}")

# Test 2: Check backend logs for table info
print("\n2. Check backend startup logs for table list")
print("   Look for: 'DEBUG: Tables in DB: [...]'")
print("   Expected: parcelles should be in the list")

print("\n" + "=" * 60)
print("Next steps:")
print("=" * 60)
print("1. Check backend terminal for 'DEBUG: Tables in DB' message")
print("2. If 'parcelles' is missing → Need to run etl_france_cadastre.py")
print("3. If 'parcelles' exists but empty → Need to load dept 35 data")
print("4. If 'parcelles' exists with data → Check spatial query")
