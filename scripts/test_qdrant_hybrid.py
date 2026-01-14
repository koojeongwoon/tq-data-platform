#!/usr/bin/env python3
"""Test script for Qdrant hybrid search with welfare data"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import requests
from shared.services.chunker import WelfareChunker
from shared.services.qdrant_service import QdrantService


def fetch_welfare_data(limit: int = 10):
    """Fetch welfare data from D1"""
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    api_token = os.getenv("CLOUDFLARE_API_TOKEN")
    database_id = os.getenv("CLOUDFLARE_D1_DB_ID")

    base_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{database_id}/query"

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "sql": f"SELECT policy_id, policy_title, raw_data FROM welfare_collections LIMIT {limit}",
        "params": [],
    }

    response = requests.post(base_url, headers=headers, json=payload)
    data = response.json()

    if data.get("success"):
        return data["result"][0]["results"]
    else:
        print(f"Error fetching data: {data}")
        return []


def main():
    print("=" * 60)
    print("🧪 Qdrant Hybrid Search Test")
    print("=" * 60)

    # 1. Fetch data from D1
    print("\n📥 Fetching welfare data from D1...")
    policies = fetch_welfare_data(limit=10)
    print(f"   Fetched {len(policies)} policies")

    if not policies:
        print("❌ No data fetched. Check D1 credentials.")
        return

    # 2. Chunk the data
    print("\n✂️ Chunking policies...")
    chunker = WelfareChunker()
    chunks = chunker.chunk_policies([
        {"policy_id": p["policy_id"], "raw_data": p["raw_data"]}
        for p in policies
    ])
    print(f"   Created {len(chunks)} chunks")

    # 3. Initialize Qdrant and create collection
    print("\n🔧 Initializing Qdrant...")
    qdrant = QdrantService(host="localhost", port=6335)
    qdrant.create_collection(recreate=True)

    # 4. Upsert chunks
    print("\n📤 Upserting chunks to Qdrant...")
    qdrant.upsert_chunks(chunks)

    # 5. Get collection info
    info = qdrant.get_collection_info()
    print(f"\n📊 Collection info: {info}")

    # 6. Test searches
    test_queries = [
        "청년 전세 대출 지원",
        "장애인 수도요금 감면",
        "출산 지원금 얼마",
        "한부모 가족 지원",
        "어떻게 신청해요?",
    ]

    print("\n" + "=" * 60)
    print("🔍 Testing Hybrid Search")
    print("=" * 60)

    for query in test_queries:
        print(f"\n🔎 Query: \"{query}\"")
        print("-" * 40)

        results = qdrant.hybrid_search(query, limit=3)

        for i, r in enumerate(results, 1):
            print(f"\n  [{i}] {r['title']}")
            print(f"      Type: {r['chunk_type']} | Score: {r['score']:.4f}")
            print(f"      Content: {r['content'][:100]}...")

    # 7. Test with filter
    print("\n" + "=" * 60)
    print("🔍 Testing with Filter (chunk_type=benefit)")
    print("=" * 60)

    results = qdrant.hybrid_search("지원금", limit=3, chunk_type="benefit")
    for i, r in enumerate(results, 1):
        print(f"\n  [{i}] {r['title']}")
        print(f"      Score: {r['score']:.4f}")
        print(f"      Content: {r['content'][:150]}...")

    print("\n✅ Test completed!")


if __name__ == "__main__":
    main()
