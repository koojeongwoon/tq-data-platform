"""Script to sync policy metadata (life_cycles, interest_themes) from PostgreSQL to Qdrant payloads"""

import asyncio
import os
import sys
from tqdm import tqdm

# Add current directory to path
sys.path.append(os.getcwd())

from shared.services.qdrant_service import QdrantService
from shared.db.postgres import PostgresClient
from shared.config.settings import settings
from qdrant_client import models

async def sync_metadata():
    print("Starting metadata sync from PostgreSQL to Qdrant...")
    
    qdrant = QdrantService(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    postgres = PostgresClient()
    
    # 1. Get all policy metadata from PostgreSQL
    print("Fetching metadata from PostgreSQL...")
    policies = postgres.execute_query(
        "SELECT policy_id, life_cycles, interest_themes FROM welfare_policies"
    )
    if not policies:
        print("No policies found in PostgreSQL.")
        return

    # Map policy_id to metadata
    metadata_map = {
        p['policy_id']: {
            'life_cycles': p['life_cycles'],
            'interest_themes': p['interest_themes']
        } for p in policies
    }
    print(f"Loaded metadata for {len(metadata_map)} policies.")

    # 2. Iterate through Qdrant points and update payload
    print(f"Scrolling through Qdrant collection: {qdrant.COLLECTION_NAME}...")
    
    offset = None
    updated_count = 0
    
    while True:
        res, next_offset = qdrant.client.scroll(
            collection_name=qdrant.COLLECTION_NAME,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False
        )
        
        for point in res:
            policy_id = point.payload.get("policy_id")
            if not policy_id or policy_id not in metadata_map:
                continue
            
            meta = metadata_map[policy_id]
            
            # Simple metadata update
            # We add it to the 'metadata' nested field to match existing structure or top-level
            # Based on previous peek, metadata contains province/city. 
            # Let's add it to the payload's metadata sub-dict if it exists, otherwise top level.
            
            new_metadata = point.payload.get("metadata", {})
            # Ensure it's not None
            if new_metadata is None: new_metadata = {}
            
            # Add life_cycle (singular, as expected by count_matches and current filters)
            # and life_cycles (array)
            new_metadata["life_cycles"] = meta["life_cycles"]
            new_metadata["interest_themes"] = meta["interest_themes"]
            
            # For simpler filtering in Qdrant (MatchValue doesn't support array easily in some versions without ANY)
            # We can also add flat fields if needed
            if meta["life_cycles"]:
                new_metadata["life_cycle"] = meta["life_cycles"][0] # Take first as primary
            
            # Update the point
            qdrant.client.set_payload(
                collection_name=qdrant.COLLECTION_NAME,
                payload={"metadata": new_metadata},
                points=[point.id]
            )
            updated_count += 1
            
        offset = next_offset
        if offset is None:
            break
            
    print(f"Successfully updated metadata for {updated_count} points in Qdrant.")

if __name__ == "__main__":
    asyncio.run(sync_metadata())
