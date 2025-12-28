"""Data synchronization service: D1 → PostgreSQL + Qdrant"""

import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, Optional

from shared.db.d1 import D1Client
from shared.db.postgres import PostgresClient
from shared.db.qdrant_client import QdrantClient
from shared.services.embedding import get_embedding_service


class PolicyCleaner:
    """Clean and normalize XML welfare policy data"""

    @staticmethod
    def extract_text(root: ET.Element, tag_name: str) -> str:
        """Extract text from XML tag"""
        elem = root.find(f".//{tag_name}")
        return elem.text.strip() if elem is not None and elem.text else ""

    @staticmethod
    def parse_date(date_str: str) -> Optional[str]:
        """
        Parse YYYYMMDD to YYYY-MM-DD

        Args:
            date_str: Date string in YYYYMMDD format

        Returns:
            ISO format date string or None
        """
        if not date_str or date_str == "99991231":  # 무기한
            return None

        try:
            dt = datetime.strptime(date_str, "%Y%m%d")
            return dt.strftime("%Y-%m-%d")
        except:
            return None

    @classmethod
    def clean_policy_xml(cls, policy_id: str, raw_xml: str, source_type: str) -> Optional[Dict[str, Any]]:
        """
        Clean XML data into structured format

        Returns:
            Dictionary with:
            - postgres_data: For keyword search
            - vector_text: For embedding
            - metadata: Common metadata
        """
        if not raw_xml:
            return None

        try:
            root = ET.fromstring(raw_xml)

            # Basic information
            title = cls.extract_text(root, "servNm")
            ministry = cls.extract_text(root, "bizChrDeptNm") or cls.extract_text(root, "jurMnofNm")
            summary = cls.extract_text(root, "servDgst")

            # Regional information
            ctpv_nm = cls.extract_text(root, "ctpvNm")  # 시도명
            sgg_nm = cls.extract_text(root, "sggNm")    # 시군구명

            # Life cycle and themes
            life_cycle_raw = cls.extract_text(root, "lifeNmArray")
            interest_theme_raw = cls.extract_text(root, "intrsThemaNmArray")

            # Convert to arrays
            life_cycles = [lc.strip() for lc in life_cycle_raw.split(",") if lc.strip()] if life_cycle_raw else []
            interest_themes = [theme.strip() for theme in interest_theme_raw.split(",") if theme.strip()] if interest_theme_raw else []

            # Support information
            support_cycle = cls.extract_text(root, "sprtCycNm")
            support_provision = cls.extract_text(root, "srvPvsnNm")
            support_content = cls.extract_text(root, "alwServCn")

            # Target information
            target_group = cls.extract_text(root, "trgterIndvdlNmArray")
            target_detail = cls.extract_text(root, "sprtTrgtCn")
            selection_criteria = cls.extract_text(root, "slctCritCn")

            # Application information
            application_method = cls.extract_text(root, "aplyMtdNm")
            application_detail = cls.extract_text(root, "aplyMtdCn")

            # Contact information
            phone = ""
            website = ""

            welfare_info_elements = list(root.iter())
            for i, elem in enumerate(welfare_info_elements):
                if elem.tag == "wlfareInfoDtlCd" and elem.text:
                    detail_code = elem.text
                    if i + 1 < len(welfare_info_elements):
                        next_elem = welfare_info_elements[i + 1]
                        if detail_code == "010" and next_elem.tag == "wlfareInfoReldCn":
                            phone = next_elem.text or ""
                        elif detail_code == "020" and next_elem.tag == "wlfareInfoReldCn":
                            website = next_elem.text or ""

            # Dates
            start_date = cls.parse_date(cls.extract_text(root, "enfcBgngYmd"))
            end_date = cls.parse_date(cls.extract_text(root, "enfcEndYmd"))

            # Create vector text (for embedding)
            vector_text_parts = [
                f"제목: {title}",
                f"요약: {summary}",
                f"지원대상: {target_detail}",
                f"선정기준: {selection_criteria}",
                f"지원내용: {support_content}",
                f"신청방법: {application_detail}",
            ]
            vector_text = " ".join([part for part in vector_text_parts if part])

            # PostgreSQL data (keyword search)
            postgres_data = {
                'policy_id': policy_id,
                'title': title,
                'ministry': ministry,
                'summary': summary,
                'source_type': source_type,
                'ctpv_nm': ctpv_nm,
                'sgg_nm': sgg_nm,
                'life_cycles': life_cycles,
                'interest_themes': interest_themes,
                'support_cycle': support_cycle,
                'support_provision': support_provision,
                'support_content': support_content,
                'target_group': target_group,
                'target_detail': target_detail,
                'selection_criteria': selection_criteria,
                'application_method': application_method,
                'application_detail': application_detail,
                'phone': phone,
                'website': website,
                'start_date': start_date,
                'end_date': end_date
            }

            # Metadata (common for both)
            metadata = {
                'title': title,
                'ministry': ministry,
                'source_type': source_type,
                'ctpv_nm': ctpv_nm,
                'sgg_nm': sgg_nm,
                'summary': summary,
                'phone': phone,
                'website': website
            }

            return {
                'postgres_data': postgres_data,
                'vector_text': vector_text,
                'metadata': metadata
            }

        except ET.ParseError as e:
            print(f"XML parsing error for policy {policy_id}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error parsing policy {policy_id}: {e}")
            return None


class DataSyncService:
    """Synchronize D1 data to PostgreSQL and Qdrant"""

    def __init__(self, use_embeddings: bool = True):
        """
        Initialize data sync service

        Args:
            use_embeddings: Whether to use BGE-M3 for embeddings (default: True)
                           Set to False for testing with placeholder vectors
        """
        self.d1 = D1Client()
        self.postgres = PostgresClient()
        self.qdrant = QdrantClient()
        self.cleaner = PolicyCleaner()
        self.use_embeddings = use_embeddings
        self.embedding_service = None

        if self.use_embeddings:
            print("🔄 Initializing BGE-M3 embedding model...")
            self.embedding_service = get_embedding_service()
            print("✅ Embedding model ready")

    def sync_all(self, batch_size: int = 100):
        """
        Sync D1 data to both PostgreSQL and Qdrant in one pass

        Args:
            batch_size: Number of policies to batch for Qdrant upsert
        """
        print("\n=== Starting Data Sync (D1 → PostgreSQL + Qdrant) ===")

        # Initialize Qdrant collection
        if not self.qdrant.init_collection():
            print("Failed to initialize Qdrant collection")
            return

        # Get all policies from D1 (single query)
        print("\n📊 Fetching policies from D1...")
        sql = "SELECT policy_id, source_type, raw_data FROM welfare_collections"
        result = self.d1.execute_query(sql)

        if not result or not result.get("success"):
            print("❌ Failed to fetch policies from D1")
            return

        try:
            policies = result.get("result", [{}])[0].get("results", [])
            print(f"✅ Fetched {len(policies)} policies from D1")
        except (IndexError, KeyError, TypeError) as e:
            print(f"❌ Error parsing D1 response: {e}")
            return

        # Get existing policy IDs in PostgreSQL
        existing_ids = self.postgres.get_existing_policy_ids()
        print(f"📌 PostgreSQL has {len(existing_ids)} existing policies")

        # Process all policies in one loop
        postgres_synced = 0
        postgres_failed = 0
        qdrant_batch = []
        qdrant_synced = 0

        print("\n🔄 Processing policies...")
        for idx, policy in enumerate(policies, 1):
            policy_id = policy.get("policy_id")
            raw_xml = policy.get("raw_data")
            source_type = policy.get("source_type")

            if not policy_id or not raw_xml:
                continue

            # Clean and parse XML (once per policy)
            cleaned = self.cleaner.clean_policy_xml(policy_id, raw_xml, source_type)

            if not cleaned:
                print(f"⚠️  Failed to clean policy {policy_id}")
                continue

            # Sync to PostgreSQL
            if self.postgres.upsert_policy(cleaned['postgres_data']):
                postgres_synced += 1
            else:
                postgres_failed += 1
                print(f"❌ Failed to sync {policy_id} to PostgreSQL")

            # Prepare for Qdrant batch
            if self.use_embeddings and self.embedding_service:
                # Generate embedding using BGE-M3
                vector = self.embedding_service.encode_single(cleaned['vector_text'])
            else:
                # Placeholder zero vector (for testing)
                vector = [0.0] * QdrantClient.VECTOR_SIZE

            qdrant_batch.append({
                'id': policy_id,
                'vector': vector,
                'metadata': cleaned['metadata']
            })

            # Batch upsert to Qdrant
            if len(qdrant_batch) >= batch_size:
                if self.qdrant.upsert_batch(qdrant_batch):
                    qdrant_synced += len(qdrant_batch)
                qdrant_batch = []

            # Progress indicator
            if idx % 100 == 0:
                print(f"Progress: {idx}/{len(policies)} policies processed")

        # Upsert remaining Qdrant batch
        if qdrant_batch:
            if self.qdrant.upsert_batch(qdrant_batch):
                qdrant_synced += len(qdrant_batch)

        # Summary
        print("\n" + "="*60)
        print("📊 Sync Summary:")
        print(f"  PostgreSQL: {postgres_synced} synced, {postgres_failed} failed")
        print(f"  Qdrant: {qdrant_synced} synced")
        print(f"  Total processed: {len(policies)} policies")
        embedding_status = "BGE-M3 embeddings" if self.use_embeddings else "Placeholder vectors"
        print(f"  Embedding: {embedding_status}")
        print("="*60)
        print("\n✅ Sync complete!")

    def sync_to_postgres(self, batch_size: int = 100):
        """
        Sync D1 data to PostgreSQL only (for backward compatibility)

        Args:
            batch_size: Not used, kept for API compatibility
        """
        print("\n--- Syncing to PostgreSQL Only ---")

        # Get all policies from D1
        sql = "SELECT policy_id, source_type, raw_data FROM welfare_collections"
        result = self.d1.execute_query(sql)

        if not result or not result.get("success"):
            print("Failed to fetch policies from D1")
            return

        try:
            policies = result.get("result", [{}])[0].get("results", [])
            print(f"Fetched {len(policies)} policies from D1")
        except (IndexError, KeyError, TypeError) as e:
            print(f"Error parsing D1 response: {e}")
            return

        # Get existing policy IDs in PostgreSQL
        existing_ids = self.postgres.get_existing_policy_ids()
        print(f"PostgreSQL has {len(existing_ids)} existing policies")

        # Process policies
        synced_count = 0
        skipped_count = 0

        for policy in policies:
            policy_id = policy.get("policy_id")
            raw_xml = policy.get("raw_data")
            source_type = policy.get("source_type")

            if not policy_id or not raw_xml:
                continue

            # Clean and parse XML
            cleaned = self.cleaner.clean_policy_xml(policy_id, raw_xml, source_type)

            if not cleaned:
                print(f"Failed to clean policy {policy_id}")
                continue

            # Upsert to PostgreSQL
            if self.postgres.upsert_policy(cleaned['postgres_data']):
                synced_count += 1
            else:
                print(f"Failed to sync {policy_id} to PostgreSQL")

            if (synced_count + skipped_count) % 100 == 0:
                print(f"Progress: {synced_count} synced, {skipped_count} skipped")

        print(f"\n✅ PostgreSQL sync complete: {synced_count} synced, {skipped_count} skipped")

    def sync_to_qdrant(self, batch_size: int = 100):
        """
        Sync D1 data to Qdrant only (for backward compatibility)

        Note: This requires an embedding model (BGE-M3)
        For now, this will prepare the data structure
        """
        print("\n--- Syncing to Qdrant Only ---")

        # Initialize collection
        if not self.qdrant.init_collection():
            print("Failed to initialize Qdrant collection")
            return

        # Get all policies from D1
        sql = "SELECT policy_id, source_type, raw_data FROM welfare_collections"
        result = self.d1.execute_query(sql)

        if not result or not result.get("success"):
            print("Failed to fetch policies from D1")
            return

        try:
            policies = result.get("result", [{}])[0].get("results", [])
            print(f"Fetched {len(policies)} policies from D1")
        except (IndexError, KeyError, TypeError) as e:
            print(f"Error parsing D1 response: {e}")
            return

        # Process policies
        synced_count = 0
        batch_points = []

        for policy in policies:
            policy_id = policy.get("policy_id")
            raw_xml = policy.get("raw_data")
            source_type = policy.get("source_type")

            if not policy_id or not raw_xml:
                continue

            # Clean and parse XML
            cleaned = self.cleaner.clean_policy_xml(policy_id, raw_xml, source_type)

            if not cleaned:
                print(f"Failed to clean policy {policy_id}")
                continue

            # TODO: Generate embedding using BGE-M3
            # For now, use placeholder zero vector
            # In production, replace with actual embedding
            vector = [0.0] * QdrantClient.VECTOR_SIZE  # Placeholder

            batch_points.append({
                'id': policy_id,
                'vector': vector,
                'metadata': cleaned['metadata']
            })

            # Batch upsert
            if len(batch_points) >= batch_size:
                if self.qdrant.upsert_batch(batch_points):
                    synced_count += len(batch_points)
                batch_points = []

        # Upsert remaining
        if batch_points:
            if self.qdrant.upsert_batch(batch_points):
                synced_count += len(batch_points)

        print(f"\n✅ Qdrant sync complete: {synced_count} policies synced")
        if not self.use_embeddings:
            print("⚠️  Note: Using placeholder vectors. Enable embeddings for production.")
