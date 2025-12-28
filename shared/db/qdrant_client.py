"""Qdrant client for vector search"""

from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient as QdrantSDK
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from shared.config.settings import settings


class QdrantClient:
    """Qdrant vector database client for semantic search"""

    COLLECTION_NAME = "welfare_policies"
    VECTOR_SIZE = 1024  # BGE-M3 embedding size

    def __init__(self):
        self.host = settings.QDRANT_HOST
        self.port = settings.QDRANT_PORT
        self.client = QdrantSDK(host=self.host, port=self.port)

    def init_collection(self):
        """Create collection if it doesn't exist"""
        try:
            # Check if collection exists
            collections = self.client.get_collections().collections
            collection_names = [col.name for col in collections]

            if self.COLLECTION_NAME not in collection_names:
                self.client.create_collection(
                    collection_name=self.COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=self.VECTOR_SIZE,
                        distance=Distance.COSINE
                    )
                )
                print(f"Created Qdrant collection: {self.COLLECTION_NAME}")
            else:
                print(f"Qdrant collection already exists: {self.COLLECTION_NAME}")

            return True
        except Exception as e:
            print(f"Error initializing Qdrant collection: {e}")
            return False

    def upsert_policy(self, policy_id: str, vector: List[float], metadata: Dict[str, Any]) -> bool:
        """
        Insert or update a single policy vector

        Args:
            policy_id: Unique policy ID
            vector: Embedding vector (1024 dimensions for BGE-M3)
            metadata: Policy metadata (title, summary, etc.)

        Returns:
            True if successful
        """
        try:
            point = PointStruct(
                id=policy_id,
                vector=vector,
                payload=metadata
            )

            self.client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=[point]
            )
            return True
        except Exception as e:
            print(f"Error upserting policy {policy_id}: {e}")
            return False

    def upsert_batch(self, points: List[Dict[str, Any]]) -> bool:
        """
        Batch insert/update policies

        Args:
            points: List of dicts with keys: id, vector, metadata

        Returns:
            True if successful
        """
        if not points:
            return True

        try:
            qdrant_points = [
                PointStruct(
                    id=point['id'],
                    vector=point['vector'],
                    payload=point['metadata']
                )
                for point in points
            ]

            self.client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=qdrant_points
            )

            print(f"Upserted {len(points)} policies to Qdrant")
            return True
        except Exception as e:
            print(f"Error batch upserting: {e}")
            return False

    def search(
        self,
        query_vector: List[float],
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Vector similarity search

        Args:
            query_vector: Query embedding vector
            filters: Optional metadata filters
            limit: Max number of results

        Returns:
            List of matching policies with scores
        """
        try:
            # Build filter if provided
            query_filter = None
            if filters:
                conditions = []

                if filters.get('source_type'):
                    conditions.append(
                        FieldCondition(
                            key="source_type",
                            match=MatchValue(value=filters['source_type'])
                        )
                    )

                if filters.get('ctpv_nm'):
                    conditions.append(
                        FieldCondition(
                            key="ctpv_nm",
                            match=MatchValue(value=filters['ctpv_nm'])
                        )
                    )

                if conditions:
                    query_filter = Filter(must=conditions)

            results = self.client.search(
                collection_name=self.COLLECTION_NAME,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=limit
            )

            return [
                {
                    'id': hit.id,
                    'score': hit.score,
                    'metadata': hit.payload
                }
                for hit in results
            ]
        except Exception as e:
            print(f"Error searching Qdrant: {e}")
            return []

    def get_policy(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """Get single policy by ID"""
        try:
            points = self.client.retrieve(
                collection_name=self.COLLECTION_NAME,
                ids=[policy_id]
            )

            if points:
                return {
                    'id': points[0].id,
                    'vector': points[0].vector,
                    'metadata': points[0].payload
                }
            return None
        except Exception as e:
            print(f"Error retrieving policy {policy_id}: {e}")
            return None

    def delete_policy(self, policy_id: str) -> bool:
        """Delete policy by ID"""
        try:
            self.client.delete(
                collection_name=self.COLLECTION_NAME,
                points_selector=[policy_id]
            )
            return True
        except Exception as e:
            print(f"Error deleting policy {policy_id}: {e}")
            return False

    def count_policies(self) -> int:
        """Get total number of policies in collection"""
        try:
            collection_info = self.client.get_collection(self.COLLECTION_NAME)
            return collection_info.points_count
        except Exception as e:
            print(f"Error counting policies: {e}")
            return 0

    def health_check(self) -> bool:
        """Check if Qdrant is accessible"""
        try:
            self.client.get_collections()
            return True
        except Exception as e:
            print(f"Qdrant health check failed: {e}")
            return False
