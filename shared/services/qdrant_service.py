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
    CACHE_COLLECTION = "llm_cache"
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

    def create_cache_collection(self, recreate: bool = False):
        """
        Create collection for semantic caching
        """
        if recreate and self.client.collection_exists(self.CACHE_COLLECTION):
            self.client.delete_collection(self.CACHE_COLLECTION)
            print(f"🗑️ Deleted existing cache collection: {self.CACHE_COLLECTION}")

        if not self.client.collection_exists(self.CACHE_COLLECTION):
            self.client.create_collection(
                collection_name=self.CACHE_COLLECTION,
                vectors_config={
                    "dense": VectorParams(
                        size=self.DENSE_DIM,
                        distance=Distance.COSINE,
                    )
                }
            )
            print(f"✅ Created cache collection: {self.CACHE_COLLECTION}")
        else:
            print(f"ℹ️ Cache collection already exists: {self.CACHE_COLLECTION}")

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
        life_cycle: Optional[str] = None,
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
            # Handle short region names
            region_full = {
                "서울": "서울특별시", "경기": "경기도", "인천": "인천광역시",
                "부산": "부산광역시", "대구": "대구광역시", "광주": "광주광역시",
                "대전": "대전광역시", "울산": "울산광역시", "세종": "세종특별자치시",
                "강원": "강원특별자치도", "충북": "충청북도", "충남": "충청남도",
                "전북": "전북특별자치도", "전남": "전라남도", "경북": "경상북도",
                "경남": "경상남도", "제주": "제주특별자치도"
            }
            full_province = region_full.get(province, province)
            
            # Include policies from the specific region OR nationwide ("전국")
            filter_conditions.append(
                Filter(
                    should=[
                        FieldCondition(key="metadata.province", match=MatchValue(value=full_province)),
                        FieldCondition(key="metadata.province", match=MatchValue(value="전국")),
                        FieldCondition(key="metadata.province", match=MatchValue(value="")),
                    ]
                )
            )

        if life_cycle:
            filter_conditions.append(
                FieldCondition(key="metadata.life_cycle", match=MatchValue(value=life_cycle))
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
            # Handle short region names
            region_full = {
                "서울": "서울특별시", "경기": "경기도", "인천": "인천광역시",
                "부산": "부산광역시", "대구": "대구광역시", "광주": "광주광역시",
                "대전": "대전광역시", "울산": "울산광역시", "세종": "세종특별자치시",
                "강원": "강원특별자치도", "충북": "충청북도", "충남": "충청남도",
                "전북": "전북특별자치도", "전남": "전라남도", "경북": "경상북도",
                "경남": "경상남도", "제주": "제주특별자치도"
            }
            full_province = region_full.get(province, province)
            filter_conditions.append(
                FieldCondition(key="metadata.province", match=MatchValue(value=full_province))
            )

        if life_cycle:
            filter_conditions.append(
                FieldCondition(key="metadata.life_cycle", match=MatchValue(value=life_cycle))
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

    def count_matches(self, province: Optional[str] = None, life_cycle: Optional[str] = None) -> int:
        """관심 지역 및 생애주기에 따른 정책 수 카운트"""
        filter_conditions = []
        
        if province:
             # Handle short region names
            region_full = {
                "서울": "서울특별시", "경기": "경기도", "인천": "인천광역시",
                "부산": "부산광역시", "대구": "대구광역시", "광주": "광주광역시",
                "대전": "대전광역시", "울산": "울산광역시", "세종": "세종특별자치시",
                "강원": "강원특별자치도", "충북": "충청북도", "충남": "충청남도",
                "전북": "전북특별자치도", "전남": "전라남도", "경북": "경상북도",
                "경남": "경상남도", "제주": "제주특별자치도"
            }
            full_province = region_full.get(province, province)
            filter_conditions.append(
                FieldCondition(key="metadata.province", match=MatchValue(value=full_province))
            )

        if life_cycle:
            filter_conditions.append(
                FieldCondition(key="metadata.life_cycle", match=MatchValue(value=life_cycle))
            )

        query_filter = Filter(must=filter_conditions) if filter_conditions else None
        
        count_result = self.client.count(
            collection_name=self.COLLECTION_NAME,
            count_filter=query_filter,
            exact=False
        )
        return count_result.count

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

    def get_cache(self, query: str, threshold: float = 0.95) -> Optional[Dict[str, Any]]:
        """
        Search for similar questions in semantic cache
        """
        if not self.client.collection_exists(self.CACHE_COLLECTION):
            return None

        dense_query = self._encode_dense_query(query)
        
        results = self.client.query_points(
            collection_name=self.CACHE_COLLECTION,
            query=dense_query,
            using="dense",
            limit=1,
            with_payload=True
        )

        if results.points and results.points[0].score >= threshold:
            point = results.points[0]
            print(f"🎯 Cache hit! Score: {point.score:.4f}")
            return {
                "answer": point.payload.get("answer"),
                "sources": point.payload.get("sources", []),
                "score": point.score,
                "original_query": point.payload.get("query")
            }
        
        return None

    def upsert_cache(self, query: str, answer: str, sources: List[Dict[str, Any]] = None):
        """
        Store question/answer pair in semantic cache
        """
        if not self.client.collection_exists(self.CACHE_COLLECTION):
            self.create_cache_collection()

        dense_vector = self._encode_dense_query(query)
        import uuid
        
        point_id = str(uuid.uuid4())
        
        self.client.upsert(
            collection_name=self.CACHE_COLLECTION,
            points=[
                PointStruct(
                    id=point_id,
                    vector={"dense": dense_vector},
                    payload={
                        "query": query,
                        "answer": answer,
                        "sources": sources or [],
                        "created_at": models.Timestamp.now() if hasattr(models, 'Timestamp') else None
                    }
                )
            ]
        )
        print(f"💾 Cached new response: {query[:30]}...")
