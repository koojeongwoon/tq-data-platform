"""
Migrate welfare policies from Cloudflare D1 to PostgreSQL

Usage:
    python scripts/migrate_d1_to_postgres.py
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.db.d1 import D1Client
from shared.db.postgres import PostgresClient


def parse_xml_data(raw_data: str, policy_id: str, source_type: str) -> dict:
    """Parse raw XML data into policy dict"""
    try:
        root = ET.fromstring(raw_data)
    except ET.ParseError as e:
        print(f"  ⚠️  XML parse error for {policy_id}: {e}")
        return None
    
    def get_text(tag: str) -> str:
        """Get text content of a tag"""
        elem = root.find(tag)
        return elem.text.strip() if elem is not None and elem.text else ""
    
    def get_array(tag: str) -> list:
        """Get array from comma-separated or multiple tags"""
        elem = root.find(tag)
        if elem is not None and elem.text:
            # Split by comma and clean up
            return [x.strip() for x in elem.text.split(",") if x.strip()]
        return []
    
    # Extract life cycles (from single field with comma-separated values)
    life_cycles = get_array("lifeNmArray")
    
    # Extract interest themes
    interest_themes = get_array("intrsThemaNmArray")
    
    return {
        "policy_id": policy_id,
        "title": get_text("servNm"),
        "ministry": get_text("jurMnofNm") or get_text("bizChrDeptNm"),
        "summary": get_text("servDgst"),
        "source_type": source_type,
        "ctpv_nm": get_text("ctpvNm"),
        "sgg_nm": get_text("sggNm"),
        "life_cycles": life_cycles if life_cycles else None,
        "interest_themes": interest_themes if interest_themes else None,
        "support_cycle": get_text("sprtCycNm"),
        "support_provision": get_text("srvPvsnNm"),
        "support_content": get_text("alwServCn"),
        "target_group": get_text("trgterIndvdlNmArray"),
        "target_detail": get_text("trgterIndvdlCn"),
        "selection_criteria": get_text("slctCritCn"),
        "application_method": get_text("aplyMtdNm"),
        "application_detail": get_text("aplyMtdCn"),
        "phone": get_text("inqNum"),
        "website": get_text("servDtlLink"),
        "start_date": None,
        "end_date": None,
    }


def migrate():
    """Main migration function"""
    print("🚀 Starting D1 to PostgreSQL migration...")
    
    d1 = D1Client()
    postgres = PostgresClient()
    
    # Check PostgreSQL connection
    if not postgres.health_check():
        print("❌ PostgreSQL connection failed. Check your settings.")
        return
    
    print("✅ PostgreSQL connected")
    
    # Fetch all policies from D1
    print("📥 Fetching policies from D1...")
    
    sql = "SELECT policy_id, source_type, raw_data FROM welfare_collections"
    result = d1.execute_query(sql)
    
    if not result or not result.get("success"):
        print("❌ Failed to fetch from D1")
        return
    
    rows = result.get("result", [{}])[0].get("results", [])
    total = len(rows)
    print(f"📊 Found {total} policies in D1")
    
    if total == 0:
        print("No data to migrate.")
        return
    
    # Migrate in batches
    success_count = 0
    error_count = 0
    batch_size = 100
    
    for i in range(0, total, batch_size):
        batch = rows[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (total + batch_size - 1) // batch_size
        
        for row in batch:
            policy_id = row.get("policy_id")
            source_type = row.get("source_type", "central")
            raw_data = row.get("raw_data")
            
            if not raw_data:
                error_count += 1
                continue
            
            policy_data = parse_xml_data(raw_data, policy_id, source_type)
            
            if not policy_data:
                error_count += 1
                continue
            
            if postgres.upsert_policy(policy_data):
                success_count += 1
            else:
                error_count += 1
                print(f"  ❌ Failed to insert {policy_id}")
        
        print(f"📦 Batch {batch_num}/{total_batches}: {success_count} success, {error_count} errors")
    
    print(f"\n🎉 Migration complete!")
    print(f"   ✅ Success: {success_count}")
    print(f"   ❌ Errors: {error_count}")
    
    # Verify count
    pg_count = postgres.count_policies()
    print(f"   📊 PostgreSQL total: {pg_count}")


if __name__ == "__main__":
    migrate()
