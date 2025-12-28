"""BGE-M3 embedding service for semantic search"""

from typing import List, Union

from sentence_transformers import SentenceTransformer


class EmbeddingService:
    """
    BGE-M3 embedding service for Korean text

    Model: BAAI/bge-m3
    - Multilingual (supports Korean well)
    - 1024 dimensions
    - Optimized for semantic search
    """

    MODEL_NAME = "BAAI/bge-m3"
    VECTOR_SIZE = 1024

    def __init__(self):
        """
        Initialize BGE-M3 model

        Note: First run will download the model (~2GB)
        """
        print(f"Loading embedding model: {self.MODEL_NAME}...")
        self.model = SentenceTransformer(self.MODEL_NAME)
        print(f"✅ Model loaded successfully (dimension: {self.VECTOR_SIZE})")

    def encode_single(self, text: str) -> List[float]:
        """
        Encode single text to embedding vector

        Args:
            text: Input text (Korean or multilingual)

        Returns:
            1024-dimensional embedding vector
        """
        if not text or not text.strip():
            # Return zero vector for empty text
            return [0.0] * self.VECTOR_SIZE

        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def encode_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Encode multiple texts to embedding vectors (batched for efficiency)

        Args:
            texts: List of input texts
            batch_size: Number of texts to process at once

        Returns:
            List of 1024-dimensional embedding vectors
        """
        if not texts:
            return []

        # Replace empty texts with placeholder to avoid errors
        processed_texts = [text if text and text.strip() else " " for text in texts]

        embeddings = self.model.encode(
            processed_texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 100  # Show progress for large batches
        )

        return embeddings.tolist()

    def encode_query(self, query: str) -> List[float]:
        """
        Encode search query to embedding vector

        For BGE models, queries can be prefixed with "query: " for better results,
        but BGE-M3 works well without it for Korean text.

        Args:
            query: Search query text

        Returns:
            1024-dimensional embedding vector
        """
        return self.encode_single(query)


# Singleton instance for reuse across the application
_embedding_service: EmbeddingService = None


def get_embedding_service() -> EmbeddingService:
    """
    Get singleton embedding service instance

    This ensures the model is loaded only once and reused.
    """
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
