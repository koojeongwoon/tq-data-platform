import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from shared.services.qdrant_service import QdrantService
from shared.config.settings import settings

def debug_qdrant_detailed():
    qservice = QdrantService(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    
    print("\n--- Checking for life_cycle/life_cycles in Metadata ---")
    points = qservice.client.scroll(
        collection_name=qservice.COLLECTION_NAME,
        limit=100,
        with_payload=True
    )[0]
    
    metadata_keys = set()
    payload_keys = set()
    points_with_lifecycle = 0
    
    for p in points:
        payload_keys.update(p.payload.keys())
        meta = p.payload.get('metadata', {})
        metadata_keys.update(meta.keys())
        if 'life_cycle' in meta or 'life_cycles' in meta or 'life_cycle' in p.payload or 'life_cycles' in p.payload:
            points_with_lifecycle += 1

    print(f"Total points checked: {len(points)}")
    print(f"Top-level payload keys found: {payload_keys}")
    print(f"Metadata keys found: {metadata_keys}")
    print(f"Points with any 'life_cycle' variant: {points_with_lifecycle}")

if __name__ == "__main__":
    debug_qdrant_detailed()
