"""Qdrant vector store service with hybrid search (Dense + Sparse BM25)"""

from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient, models
from qdrant_client.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    PointStruct,
    SparseVector,
    NamedVector,
    NamedSparseVector,
    Filter,
    FieldCondition,
    MatchValue,
    SearchRequest,
    Prefetch,
    FusionQuery,
    Fusion,
)


class QdrantService:
    """
    Qdrant service for hybrid search using:
    - Dense: multilingual-e5-large (1024 dim)
    - Sparse: FastEmbed BM25
    """

    COLLECTION_NAME = "welfare_chunks"
    DENSE_MODEL = "intfloat/multilingual-e5-large"
    SPARSE_MODEL = "Qdrant/bm25"
    DENSE_DIM = 1024

    def __init__(self, host: str = "localhost", port: int = 6335):
        """
        Initialize Qdrant client with FastEmbed support

        Args:
            host: Qdrant server host
            port: Qdrant server port
        """
        self.client = QdrantClient(host=host, port=port)
        self._dense_model = None
        self._sparse_model = None

    def _get_dense_model(self):
        """Lazy load dense embedding model"""
        if self._dense_model is None:
            from fastembed import TextEmbedding
            print(f"Loading dense model: {self.DENSE_MODEL}...")
            self._dense_model = TextEmbedding(model_name=self.DENSE_MODEL)
            print("✅ Dense model loaded")
        return self._dense_model

    def _get_sparse_model(self):
        """Lazy load sparse embedding model"""
        if self._sparse_model is None:
            from fastembed import SparseTextEmbedding
            print(f"Loading sparse model: {self.SPARSE_MODEL}...")
            self._sparse_model = SparseTextEmbedding(model_name=self.SPARSE_MODEL)
            print("✅ Sparse model loaded")
        return self._sparse_model

    def create_collection(self, recreate: bool = False):
        """
        Create collection with hybrid vector configuration

        Args:
            recreate: If True, delete existing collection first
        """
        if recreate and self.client.collection_exists(self.COLLECTION_NAME):
            self.client.delete_collection(self.COLLECTION_NAME)
            print(f"🗑️ Deleted existing collection: {self.COLLECTION_NAME}")

        if not self.client.collection_exists(self.COLLECTION_NAME):
            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config={
                    "dense": VectorParams(
                        size=self.DENSE_DIM,
                        distance=Distance.COSINE,
                    )
                },
                sparse_vectors_config={
                    "sparse": SparseVectorParams()
                },
            )
            print(f"✅ Created collection: {self.COLLECTION_NAME}")
        else:
            print(f"ℹ️ Collection already exists: {self.COLLECTION_NAME}")

    def _encode_dense(self, texts: List[str]) -> List[List[float]]:
        """Encode texts using dense model with E5 prefix"""
        model = self._get_dense_model()
        # E5 requires "passage: " prefix for documents
        prefixed = [f"passage: {text}" for text in texts]
        embeddings = list(model.embed(prefixed))
        return [emb.tolist() for emb in embeddings]

    def _encode_dense_query(self, query: str) -> List[float]:
        """Encode query using dense model with E5 prefix"""
        model = self._get_dense_model()
        # E5 requires "query: " prefix for queries
        embeddings = list(model.embed([f"query: {query}"]))
        return embeddings[0].tolist()

    def _encode_sparse(self, texts: List[str]) -> List[SparseVector]:
        """Encode texts using sparse BM25 model"""
        model = self._get_sparse_model()
        embeddings = list(model.embed(texts))
        return [
            SparseVector(indices=emb.indices.tolist(), values=emb.values.tolist())
            for emb in embeddings
        ]

    def _encode_sparse_query(self, query: str) -> SparseVector:
        """Encode query using sparse BM25 model"""
        model = self._get_sparse_model()
        embeddings = list(model.embed([query]))
        emb = embeddings[0]
        return SparseVector(indices=emb.indices.tolist(), values=emb.values.tolist())

    def upsert_chunks(self, chunks: List[Dict[str, Any]], batch_size: int = 100, n_workers: int = 2):
        """
        Upsert chunks to Qdrant with both dense and sparse vectors

        Args:
            chunks: List of chunk dictionaries from WelfareChunker
            batch_size: Number of chunks to process at once
            n_workers: Number of parallel workers for embedding
        """
        from concurrent.futures import ThreadPoolExecutor
        
        total = len(chunks)
        print(f"📥 Upserting {total} chunks (batch_size={batch_size}, workers={n_workers})...")

        for i in range(0, total, batch_size):
            batch = chunks[i:i + batch_size]
            contents = [c["content"] for c in batch]

            # Generate embeddings in parallel
            with ThreadPoolExecutor(max_workers=n_workers) as executor:
                dense_future = executor.submit(self._encode_dense, contents)
                sparse_future = executor.submit(self._encode_sparse, contents)
                
                dense_vectors = dense_future.result()
                sparse_vectors = sparse_future.result()

            # Create points
            points = []
            for j, chunk in enumerate(batch):
                point = PointStruct(
                    id=hash(chunk["chunk_id"]) & 0x7FFFFFFFFFFFFFFF,  # Positive int64
                    vector={
                        "dense": dense_vectors[j],
                        "sparse": sparse_vectors[j],
                    },
                    payload={
                        "chunk_id": chunk["chunk_id"],
                        "chunk_type": chunk["chunk_type"],
                        "policy_id": chunk["policy_id"],
                        "title": chunk["title"],
                        "content": chunk["content"],
                        "metadata": chunk.get("metadata", {}),
                    },
                )
                points.append(point)

            self.client.upsert(collection_name=self.COLLECTION_NAME, points=points)
            print(f"  ✅ {min(i + batch_size, total)}/{total}")

        print(f"✅ Upserted {total} chunks successfully")

    def hybrid_search(
        self,
        query: str,
        limit: int = 5,
        chunk_type: Optional[str] = None,
        province: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search using RRF (Reciprocal Rank Fusion)

        Args:
            query: Search query
            limit: Number of results
            chunk_type: Filter by chunk type (basic_info, eligibility, benefit, application)
            province: Filter by province (e.g., "서울특별시", "경기도")

        Returns:
            List of search results with score and payload
        """
        # Build filter
        filter_conditions = []
        if chunk_type:
            filter_conditions.append(
                FieldCondition(key="chunk_type", match=MatchValue(value=chunk_type))
            )
        if province:
            filter_conditions.append(
                FieldCondition(key="metadata.province", match=MatchValue(value=province))
            )

        query_filter = Filter(must=filter_conditions) if filter_conditions else None

        # Encode query
        dense_query = self._encode_dense_query(query)
        sparse_query = self._encode_sparse_query(query)

        # Hybrid search with RRF fusion
        results = self.client.query_points(
            collection_name=self.COLLECTION_NAME,
            prefetch=[
                Prefetch(
                    query=dense_query,
                    using="dense",
                    limit=limit * 2,
                    filter=query_filter,
                ),
                Prefetch(
                    query=sparse_query,
                    using="sparse",
                    limit=limit * 2,
                    filter=query_filter,
                ),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=limit,
        )

        return [
            {
                "score": point.score,
                "chunk_id": point.payload.get("chunk_id"),
                "chunk_type": point.payload.get("chunk_type"),
                "policy_id": point.payload.get("policy_id"),
                "title": point.payload.get("title"),
                "content": point.payload.get("content"),
                "metadata": point.payload.get("metadata", {}),
            }
            for point in results.points
        ]

    def search_dense_only(
        self,
        query: str,
        limit: int = 5,
        chunk_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Dense-only search (semantic)"""
        dense_query = self._encode_dense_query(query)

        filter_conditions = []
        if chunk_type:
            filter_conditions.append(
                FieldCondition(key="chunk_type", match=MatchValue(value=chunk_type))
            )
        query_filter = Filter(must=filter_conditions) if filter_conditions else None

        results = self.client.search(
            collection_name=self.COLLECTION_NAME,
            query_vector=NamedVector(name="dense", vector=dense_query),
            query_filter=query_filter,
            limit=limit,
        )

        return [
            {
                "score": point.score,
                "chunk_id": point.payload.get("chunk_id"),
                "chunk_type": point.payload.get("chunk_type"),
                "policy_id": point.payload.get("policy_id"),
                "title": point.payload.get("title"),
                "content": point.payload.get("content"),
            }
            for point in results
        ]

    def search_sparse_only(
        self,
        query: str,
        limit: int = 5,
        chunk_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Sparse-only search (BM25 keyword)"""
        sparse_query = self._encode_sparse_query(query)

        filter_conditions = []
        if chunk_type:
            filter_conditions.append(
                FieldCondition(key="chunk_type", match=MatchValue(value=chunk_type))
            )
        query_filter = Filter(must=filter_conditions) if filter_conditions else None

        results = self.client.search(
            collection_name=self.COLLECTION_NAME,
            query_vector=NamedSparseVector(name="sparse", vector=sparse_query),
            query_filter=query_filter,
            limit=limit,
        )

        return [
            {
                "score": point.score,
                "chunk_id": point.payload.get("chunk_id"),
                "chunk_type": point.payload.get("chunk_type"),
                "policy_id": point.payload.get("policy_id"),
                "title": point.payload.get("title"),
                "content": point.payload.get("content"),
            }
            for point in results
        ]

    def get_collection_info(self) -> Dict[str, Any]:
        """Get collection information"""
        info = self.client.get_collection(self.COLLECTION_NAME)
        return {
            "name": self.COLLECTION_NAME,
            "points_count": info.points_count,
            "status": info.status,
        }
