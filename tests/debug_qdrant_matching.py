import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from shared.services.qdrant_service import QdrantService
from shared.config.settings import settings

def debug_qdrant():
    qservice = QdrantService(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    
    # 1. Check collection info
    print("--- Collection Info ---")
    try:
        info = qservice.get_collection_info()
        print(f"Points count: {info['points_count']}")
    except Exception as e:
        print(f"Error getting collection info: {e}")
        return

    # 2. Inspect sample points
    from qdrant_client import models
    print("\n--- Sample Points ---")
    points = qservice.client.scroll(
        collection_name=qservice.COLLECTION_NAME,
        limit=3,
        with_payload=True,
        with_vectors=False
    )[0]
    
    for p in points:
        print(f"ID: {p.id}")
        print(f"Payload keys: {list(p.payload.keys())}")
        if 'metadata' in p.payload:
            print(f"Metadata: {p.payload['metadata']}")
        print("-" * 20)

    # 3. Test filtering logic
    print("\n--- Testing Filter Logic ---")
    # Let's try to find what values exist for province and life_cycle
    # We'll just scroll more to see patterns
    all_points = qservice.client.scroll(
        collection_name=qservice.COLLECTION_NAME,
        limit=50,
        with_payload=True
    )[0]
    
    provinces = set()
    life_cycles = set()
    for p in all_points:
        meta = p.payload.get('metadata', {})
        if 'province' in meta: provinces.add(meta['province'])
        if 'life_cycle' in meta: life_cycles.add(meta['life_cycle'])
        # Also check if it's in top level
        if 'province' in p.payload: provinces.add(p.payload['province'])
        if 'life_cycle' in p.payload: life_cycles.add(p.payload['life_cycle'])

    print(f"Provinces found in first 50 points: {provinces}")
    print(f"Life cycles found in first 50 points: {life_cycles}")

    # 4. Test count_matches with a known value
    if provinces:
        p = list(provinces)[0]
        count = qservice.count_matches(province=p)
        print(f"Count for province '{p}': {count}")
    
    if life_cycles:
        lc = list(life_cycles)[0]
        count = qservice.count_matches(life_cycle=lc)
        print(f"Count for life_cycle '{lc}': {count}")

if __name__ == "__main__":
    debug_qdrant()
