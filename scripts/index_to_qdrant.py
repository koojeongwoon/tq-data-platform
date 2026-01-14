"""
Index welfare policies to Qdrant from PostgreSQL

Usage:
    python scripts/index_to_qdrant.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.db.postgres import PostgresClient
from shared.services.qdrant_service import QdrantService
from shared.config.settings import settings


def build_chunks_from_policy(policy: dict) -> list:
    """Build semantic chunks from PostgreSQL policy data"""
    policy_id = policy["policy_id"]
    title = policy.get("title", "")
    province = policy.get("ctpv_nm", "")
    city = policy.get("sgg_nm", "")
    
    chunks = []
    
    # === Chunk 1: Basic Info ===
    basic_content = f"""[{title}]
요약: {policy.get('summary', '')}
담당부처: {policy.get('ministry', '')}
지역: {province} {city}
생애주기: {', '.join(policy.get('life_cycles', []) or [])}
주제: {', '.join(policy.get('interest_themes', []) or [])}
지원주기: {policy.get('support_cycle', '')}
지원형태: {policy.get('support_provision', '')}"""

    chunks.append({
        "chunk_id": f"{policy_id}_basic",
        "chunk_type": "basic_info",
        "policy_id": policy_id,
        "title": title,
        "content": basic_content,
        "metadata": {"province": province, "city": city},
    })

    # === Chunk 2: Eligibility ===
    target = policy.get("target_detail", "")
    criteria = policy.get("selection_criteria", "")
    
    if target or criteria:
        eligibility_text = ""
        if target:
            eligibility_text += f"지원대상:\n{target}"
        if criteria:
            if eligibility_text:
                eligibility_text += "\n\n"
            eligibility_text += f"선정기준:\n{criteria}"
        
        chunks.append({
            "chunk_id": f"{policy_id}_eligibility",
            "chunk_type": "eligibility",
            "policy_id": policy_id,
            "title": title,
            "content": f"[{title}] - 누가 받을 수 있나요?\n\n{eligibility_text}",
            "metadata": {"province": province, "city": city},
        })

    # === Chunk 3: Benefit ===
    benefit = policy.get("support_content", "")
    
    if benefit:
        chunks.append({
            "chunk_id": f"{policy_id}_benefit",
            "chunk_type": "benefit",
            "policy_id": policy_id,
            "title": title,
            "content": f"[{title}] - 무엇을 받을 수 있나요?\n\n지원내용:\n{benefit}",
            "metadata": {
                "province": province,
                "city": city,
                "support_provision": policy.get("support_provision", ""),
            },
        })

    # === Chunk 4: Application ===
    apply_method = policy.get("application_detail", "")
    apply_type = policy.get("application_method", "")
    phone = policy.get("phone", "")
    
    if apply_method or apply_type or phone:
        apply_content = ""
        if apply_type:
            apply_content += f"신청방법: {apply_type}\n\n"
        if apply_method:
            apply_content += apply_method
        if phone:
            apply_content += f"\n\n문의처: {phone}"
        
        chunks.append({
            "chunk_id": f"{policy_id}_application",
            "chunk_type": "application",
            "policy_id": policy_id,
            "title": title,
            "content": f"[{title}] - 어떻게 신청하나요?\n\n{apply_content}",
            "metadata": {"province": province, "city": city},
        })

    return chunks


def index_policies():
    """Main indexing function"""
    print("🚀 Starting Qdrant indexing from PostgreSQL...")
    
    postgres = PostgresClient()
    qdrant = QdrantService(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    
    # Check PostgreSQL connection
    if not postgres.health_check():
        print("❌ PostgreSQL connection failed.")
        return
    
    print("✅ PostgreSQL connected")
    
    # Create collection
    print("📦 Creating Qdrant collection...")
    qdrant.create_collection(recreate=True)
    
    # Fetch all policies from PostgreSQL
    print("📥 Fetching policies from PostgreSQL...")
    sql = "SELECT * FROM welfare_policies"
    rows = postgres.execute_query(sql)
    
    if not rows:
        print("❌ No data found in PostgreSQL")
        return
    
    total = len(rows)
    print(f"📊 Found {total} policies in PostgreSQL")
    
    # Process in batches
    batch_size = 100
    total_chunks = 0
    
    for i in range(0, total, batch_size):
        batch = rows[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (total + batch_size - 1) // batch_size
        
        print(f"\n📦 Processing batch {batch_num}/{total_batches}...")
        
        # Build chunks from policies
        all_chunks = []
        for policy in batch:
            chunks = build_chunks_from_policy(policy)
            all_chunks.extend(chunks)
        
        if not all_chunks:
            print(f"  ⚠️  No valid chunks in batch")
            continue
        
        # Upsert to Qdrant (includes embedding generation)
        qdrant.upsert_chunks(all_chunks, batch_size=100, n_workers=2)
        total_chunks += len(all_chunks)
        
        print(f"  ✅ Indexed {len(all_chunks)} chunks (total: {total_chunks})")
    
    print(f"\n🎉 Indexing complete!")
    print(f"   📊 Total chunks indexed: {total_chunks}")
    
    # Verify
    info = qdrant.get_collection_info()
    print(f"   📊 Qdrant collection: {info['points_count']} points")


if __name__ == "__main__":
    index_policies()
