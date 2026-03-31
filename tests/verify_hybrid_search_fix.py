import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from shared.services.qdrant_service import QdrantService
from shared.config.settings import settings

def verify_hybrid_search():
    qservice = QdrantService(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    
    # Test with short province name
    province = "서울"
    query = "청년 복지 정책"
    
    print(f"\n--- Testing Hybrid Search with province='{province}' ---")
    results = qservice.hybrid_search(
        query=query,
        limit=5,
        province=province
    )
    
    print(f"Results found: {len(results)}")
    for i, res in enumerate(results):
        print(f"[{i+1}] Score: {res['score']:.4f}, Title: {res['payload'].get('title')}")
        print(f"    Region: {res['payload'].get('metadata', {}).get('province')}")

    if len(results) == 0:
        print("Test FAILED: No results found for '서울'")
    else:
        print("Test PASSED: Results found for '서울'")

if __name__ == "__main__":
    verify_hybrid_search()
